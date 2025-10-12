"""Actor enrichment engine for world simulation."""
import json
import re
import time
from openai import OpenAI
from typing import Dict, Any
import weave

from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, ENRICHMENT_MODEL, ENRICHMENT_MAX_TOKENS
from src.prompts import ACTOR_ENRICHMENT_SYSTEM, ACTOR_ENRICHMENT_USER
from src.tools.tavily_search import search_for_actor_context

MAX_RETRIES = 3


class ActorEnricher:
    """Enriches actors with detailed profiles using research."""
    
    def __init__(self):
        """Initialize the actor enricher with OpenRouter client."""
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        self.model = ENRICHMENT_MODEL
        self.max_tokens = ENRICHMENT_MAX_TOKENS
    
    @weave.op()
    def enrich(self, actor: Dict[str, Any]) -> Dict[str, str]:
        """
        Enrich an actor with detailed profile.
        
        Args:
            actor: Actor dictionary with identifier, research_query, etc.
            
        Returns:
            Dictionary with memory, intrinsic_characteristics, predispositions
        """
        identifier = actor.get('identifier', 'Unknown')
        print(f"🔍 Enriching actor: {identifier} using {self.model}...")
        
        # Optional: Add real-time search context via Tavily
        research_query = actor.get('research_query', '')
        search_context = ""
        if research_query:
            tavily_results = search_for_actor_context(research_query, max_results=2)
            if tavily_results:
                search_context = f"\n\nReal-time web search results:\n{tavily_results}"
                print(f"  ✅ Added Tavily search context")
        
        user_prompt = ACTOR_ENRICHMENT_USER.format(
            identifier=identifier,
            research_query=actor.get('research_query', '') + search_context,
            role_in_simulation=actor.get('role_in_simulation', ''),
            granularity=actor.get('granularity', ''),
            scale_notes=actor.get('scale_notes', '')
        )
        
        # Retry loop for LLM calls
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": ACTOR_ENRICHMENT_SYSTEM},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.7,
                )
                
                response_text = response.choices[0].message.content
                
                # Extract JSON from response
                enrichment_data = self._extract_json(response_text)
                
                token_count = len(response_text.split())
                print(f"✅ Enriched {identifier} (~{token_count} words)")
                
                return enrichment_data
                
            except (ValueError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                print(f"⚠️  Attempt {attempt}/{MAX_RETRIES} failed for {identifier}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # Brief delay before retry
                continue
        
        # If all retries failed, raise the last error
        print(f"❌ All {MAX_RETRIES} attempts failed for enriching {identifier}")
        raise last_error
    
    def _extract_json(self, text: str) -> Dict[str, str]:
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
                # If no JSON found, create structure from text
                print("⚠️  No JSON found, creating structure from text")
                return {
                    "memory": text[:len(text)//3],
                    "intrinsic_characteristics": text[len(text)//3:2*len(text)//3],
                    "predispositions": text[2*len(text)//3:]
                }
            
            json_str = text[start:end+1]
        
        try:
            data = json.loads(json_str)
            # Validate required fields
            if not all(k in data for k in ['memory', 'intrinsic_characteristics', 'predispositions']):
                raise ValueError("Missing required fields")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️  JSON parsing failed: {e}, using fallback")
            # Fallback: split text into sections
            sections = text.split('\n\n')
            return {
                "memory": '\n\n'.join(sections[:len(sections)//3]) if sections else "No memory available",
                "intrinsic_characteristics": '\n\n'.join(sections[len(sections)//3:2*len(sections)//3]) if sections else "No characteristics available",
                "predispositions": '\n\n'.join(sections[2*len(sections)//3:]) if sections else "No predispositions available"
            }

