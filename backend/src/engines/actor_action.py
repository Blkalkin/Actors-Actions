"""Actor action engine for generating actor decisions."""
import json
import re
import time
from openai import OpenAI
from typing import Dict, Any
from datetime import datetime

from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, ACTOR_ACTION_MODEL
from src.prompts import ACTOR_ACTION_SYSTEM, ACTOR_ACTION_USER

MAX_RETRIES = 3


class ActorActionEngine:
    """Generates actor action decisions based on their state and history."""
    
    def __init__(self):
        """Initialize the actor action engine with OpenRouter client."""
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        self.model = ACTOR_ACTION_MODEL
    
    def generate_action(
        self, 
        actor: Dict[str, Any],
        actor_state: Dict[str, Any],
        question: str,
        time_unit: str,
        current_round: int,
        simulation_duration: int
    ) -> Dict[str, Any]:
        """
        Generate an action decision for an actor.
        
        The actor can see:
        - Their profile (memory, characteristics, predispositions)
        - Current world state and observations
        - Their full action history (my_actions) with outcomes and reasoning
        - Available actions and resources
        - Messages received
        
        Args:
            actor: Static actor profile
            actor_state: Current actor state (includes my_actions history)
            question: Original simulation question
            time_unit: Time unit for simulation
            current_round: Current round number
            simulation_duration: Total simulation duration
            
        Returns:
            Dict with:
                - action: The action to take
                - reasoning: Private reasoning
                - execute_round: When to execute (current or future)
                - duration: How many rounds it takes
        """
        print(f"\n🎭 Generating action for {actor['identifier']} (round {current_round})")
        
        # Build prompt with all actor context
        prompt = self._build_prompt(
            actor, actor_state, question, time_unit, 
            current_round, simulation_duration
        )
        
        # Retry loop for LLM calls
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Call actor action model
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": ACTOR_ACTION_SYSTEM},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2000,
                    temperature=0.9,
                )
                
                response_text = response.choices[0].message.content
                
                # Extract and validate JSON
                action_decision = self._extract_json(response_text)
                self._validate_action_decision(action_decision)
                
                # Log based on format (new format has 'actions' key, old has 'action')
                if 'actions' in action_decision:
                    # New format
                    action_count = len(action_decision.get('actions', []))
                    message_count = len(action_decision.get('messages', []))
                    print(f"✅ Generated {action_count} action(s) and {message_count} message(s)")
                    
                    for i, action in enumerate(action_decision.get('actions', [])):
                        print(f"   Action {i+1}: {action['action'][:60]}... (Round {action['execute_round']}, Duration: {action['duration']})")
                    
                    for i, msg in enumerate(action_decision.get('messages', [])):
                        print(f"   Message {i+1} → {msg['to_actor_id']}: {msg['content'][:60]}...")
                else:
                    # Old format (backwards compatibility)
                    print(f"✅ Action generated: {action_decision['action'][:60]}...")
                    print(f"   Execute: Round {action_decision['execute_round']}, Duration: {action_decision['duration']}")
                
                return action_decision
                
            except (ValueError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                print(f"⚠️  Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(1)  # Brief delay before retry
                continue
        
        # If all retries failed, raise the last error
        print(f"❌ All {MAX_RETRIES} attempts failed for {actor['identifier']}")
        raise last_error
    
    def _build_prompt(
        self,
        actor: Dict,
        actor_state: Dict,
        question: str,
        time_unit: str,
        current_round: int,
        simulation_duration: int
    ) -> str:
        """Build prompt with full actor context."""
        
        # Format action history for display
        action_history = self._format_action_history(actor_state.get('my_actions', []))
        
        # Format available actions
        available_actions = actor_state.get('available_actions', [])
        if not available_actions:
            available_actions = ["Any action appropriate to your role"]
        
        # Format other actors for messaging
        other_actors = actor_state.get('other_actors', [])
        if other_actors:
            other_actors_text = '\n'.join(
                f"- {a['identifier']} ({a['role']}, {a['granularity']})"
                for a in other_actors
            )
        else:
            other_actors_text = "No other actors available for messaging."
        
        prompt = ACTOR_ACTION_USER.format(
            question=question,
            time_unit=time_unit,
            current_round=current_round,
            simulation_duration=simulation_duration,
            actor_identifier=actor['identifier'],
            actor_role=actor['role_in_simulation'],
            actor_granularity=actor['granularity'],
            memory=actor.get('memory', 'Not yet enriched'),
            characteristics=actor.get('intrinsic_characteristics', 'Not yet enriched'),
            predispositions=actor.get('predispositions', 'Not yet enriched'),
            other_actors=other_actors_text,
            world_state=actor_state.get('world_state_summary', 'Initial state'),
            observations=actor_state.get('observations', 'No specific observations yet'),
            action_history=action_history,
            available_actions='\n'.join(f"- {a}" for a in available_actions),
            resources=json.dumps(actor_state.get('resources', {}), indent=2),
            constraints='\n'.join(f"- {c}" for c in actor_state.get('constraints', [])),
            messages=json.dumps(actor_state.get('messages_received', []), indent=2),
            direct_impacts=actor_state.get('direct_impacts', 'None yet'),
            indirect_impacts=actor_state.get('indirect_impacts', 'None yet')
        )
        
        return prompt
    
    def _format_action_history(self, my_actions: list) -> str:
        """Format action history for display in prompt."""
        if not my_actions:
            return "No actions taken yet."
        
        history_lines = []
        for action_item in my_actions:
            status_emoji = {
                "queued": "⏰",
                "executing": "⏳",
                "completed": "✅",
                "cancelled": "❌"
            }.get(action_item.get('status', 'unknown'), "❓")
            
            round_num = action_item.get('scheduled_round', '?')
            duration = action_item.get('duration', 1)
            action = action_item.get('action', 'Unknown')
            reasoning = action_item.get('reasoning', 'No reasoning recorded')
            status = action_item.get('status', 'unknown')
            
            history_lines.append(f"\n{status_emoji} Round {round_num} (duration: {duration}, status: {status})")
            history_lines.append(f"   Action: {action}")
            history_lines.append(f"   Your Reasoning: {reasoning}")
            
            if status == "completed":
                outcome = action_item.get('outcome', 'UNKNOWN')
                quality = action_item.get('outcome_quality', '')
                explanation = action_item.get('outcome_explanation', '')
                history_lines.append(f"   Outcome: {outcome} ({quality})")
                history_lines.append(f"   Result: {explanation}")
        
        return '\n'.join(history_lines)
    
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
                raise ValueError("No JSON found in actor action response")
            
            json_str = text[start:end+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {json_str[:200]}...")
            raise ValueError(f"Invalid JSON in actor action response: {e}")
    
    def _validate_action_decision(self, decision: Dict) -> None:
        """Validate the action decision structure (supports new format with actions and messages arrays)."""
        # Support both old format (single action) and new format (arrays)
        # Old format: {"action": "...", "reasoning": "...", "execute_round": N, "duration": N}
        # New format: {"actions": [...], "messages": [...]}
        
        # Check if this is new format
        if 'actions' in decision or 'messages' in decision:
            # New format validation
            if 'actions' not in decision:
                decision['actions'] = []
            if 'messages' not in decision:
                decision['messages'] = []
            
            # Validate actions array
            if not isinstance(decision['actions'], list):
                raise ValueError("Actions must be an array")
            
            for i, action in enumerate(decision['actions']):
                required = ['action', 'reasoning', 'execute_round', 'duration']
                for field in required:
                    if field not in action:
                        raise ValueError(f"Action {i}: missing field '{field}'")
                
                if not isinstance(action['execute_round'], int) or action['execute_round'] < 0:
                    raise ValueError(f"Action {i}: execute_round must be non-negative integer")
                if not isinstance(action['duration'], int) or action['duration'] < 1:
                    raise ValueError(f"Action {i}: duration must be ≥1")
                if len(action['action']) > 100:
                    raise ValueError(f"Action {i}: action must be ≤100 characters")
            
            # Validate messages array
            if not isinstance(decision['messages'], list):
                raise ValueError("Messages must be an array")
            
            for i, msg in enumerate(decision['messages']):
                required = ['to_actor_id', 'content', 'reasoning']
                for field in required:
                    if field not in msg:
                        raise ValueError(f"Message {i}: missing field '{field}'")
                
                if len(msg['content']) > 200:
                    raise ValueError(f"Message {i}: content must be ≤200 characters")
        else:
            # Old format validation (backwards compatibility)
            required_fields = ['action', 'reasoning', 'execute_round', 'duration']
            
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"Missing required field in action decision: {field}")
            
            if not isinstance(decision['action'], str):
                raise ValueError("Action must be a string")
            if not isinstance(decision['reasoning'], str):
                raise ValueError("Reasoning must be a string")
            if not isinstance(decision['execute_round'], int):
                raise ValueError("Execute_round must be an integer")
            if not isinstance(decision['duration'], int):
                raise ValueError("Duration must be an integer")
            
            if len(decision['action']) > 100:
                raise ValueError("Action must be ≤100 characters")
            if decision['duration'] < 1:
                raise ValueError("Duration must be ≥1")

