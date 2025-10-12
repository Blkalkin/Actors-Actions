"""Actor generation engine for world simulation."""
import json
import re
import time
import uuid
from openai import OpenAI
from typing import Dict, Any
import weave

from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, ACTOR_GENERATION_MODEL
from src.prompts import ACTOR_GENERATION_SYSTEM, ACTOR_GENERATION_USER

MAX_RETRIES = 3


class ActorGenerator:
    """Generates actors for a world simulation based on a question."""
    
    def __init__(self):
        """Initialize the actor generator with OpenRouter client."""
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        self.model = ACTOR_GENERATION_MODEL
    
    @weave.op()
    def generate(self, question: str) -> Dict[str, Any]:
        """
        Generate actors for a given question/situation.
        
        Args:
            question: The social question or situation to simulate
            
        Returns:
            Dictionary containing time_unit, simulation_duration, and actors array
        """
        print(f"🤖 Generating actors using {self.model}...")
        
        user_prompt = ACTOR_GENERATION_USER.format(question=question)
        
        # Retry loop for LLM calls
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": ACTOR_GENERATION_SYSTEM},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=4000,
                    temperature=1.0,
                )
                
                response_text = response.choices[0].message.content
                print(f"✅ Received response ({len(response_text)} chars)")
                
                # Extract and validate JSON
                actors_data = self._extract_json(response_text)
                self._validate_actors_data(actors_data)
                
                # Assign unique actor_ids to each actor
                for actor in actors_data['actors']:
                    if 'actor_id' not in actor:
                        actor['actor_id'] = str(uuid.uuid4())
                
                print(f"✅ Generated {len(actors_data['actors'])} actors")
                print(f"   Time unit: {actors_data['time_unit']}")
                print(f"   Duration: {actors_data['simulation_duration']} {actors_data['time_unit']}s")
                
                return actors_data
                
            except (ValueError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                print(f"⚠️  Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # Brief delay before retry
                continue
        
        # If all retries failed, raise the last error
        print(f"❌ All {MAX_RETRIES} attempts failed for actor generation")
        raise last_error
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from the model's response."""
        # Try to find JSON in code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if matches:
            json_str = matches[-1]
        else:
            # Find raw JSON
            start = text.find('{')
            end = text.rfind('}')
            
            if start == -1 or end == -1:
                raise ValueError("No JSON found in response")
            
            json_str = text[start:end+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {json_str[:200]}...")
            raise ValueError(f"Invalid JSON in response: {e}")
    
    def _validate_actors_data(self, data: Dict[str, Any]) -> None:
        """Validate the structure of the actors data."""
        required_fields = ['time_unit', 'simulation_duration', 'actors']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        if not isinstance(data['actors'], list) or len(data['actors']) == 0:
            raise ValueError("Must have at least one actor")
        
        # Validate each actor
        actor_ids = set()
        for i, actor in enumerate(data['actors']):
            self._validate_actor(actor, i)
            actor_ids.add(actor['identifier'])
        
        # Validate key_interactions references
        for actor in data['actors']:
            for interaction in actor.get('key_interactions', []):
                if interaction not in actor_ids:
                    print(f"⚠️  Warning: {actor['identifier']} references unknown actor: {interaction}")
    
    def _validate_actor(self, actor: Dict[str, Any], index: int) -> None:
        """Validate a single actor's structure."""
        required_fields = [
            'identifier', 'research_query', 'granularity',
            'scale_notes', 'role_in_simulation', 'key_interactions'
        ]
        
        for field in required_fields:
            if field not in actor:
                raise ValueError(f"Actor {index} missing required field: {field}")
        
        if not isinstance(actor['key_interactions'], list):
            raise ValueError(f"Actor {index} 'key_interactions' must be a list")

