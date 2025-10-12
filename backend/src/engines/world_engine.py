"""World engine for processing actor actions through time using action queue."""
import json
import re
import time
from openai import OpenAI
from typing import Dict, Any, List
from datetime import datetime

from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, WORLD_ENGINE_MODEL
from src.prompts import WORLD_ENGINE_SYSTEM, WORLD_ENGINE_USER
from src.storage import get_storage

MAX_RETRIES = 3


class WorldEngine:
    """Processes actor actions and maintains world state using action scheduling."""
    
    def __init__(self):
        """Initialize the world engine with OpenRouter client."""
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        self.model = WORLD_ENGINE_MODEL
    
    def process_round(self, simulation_id: str, round_number: int) -> Dict[str, Any]:
        """
        Process a round of the simulation using the action queue.
        
        Flow:
        1. Get scheduled actions for this round
        2. Get active multi-round actions (for context)
        3. Build prompt with current state
        4. Call LLM to process actions
        5. Update action statuses and create actor states
        6. Handle multi-round action tracking
        
        Args:
            simulation_id: The simulation ID
            round_number: Current round number
            
        Returns:
            Dict containing:
                - round_data: Public Round data
                - actor_states: Updated ActorState for each actor
        """
        storage = get_storage()
        
        print(f"\n{'='*80}")
        print(f"🌍 World Engine Processing Round {round_number}")
        print(f"{'='*80}\n")
        
        # Get simulation data
        sim = storage.get_simulation(simulation_id)
        if not sim:
            raise ValueError(f"Simulation {simulation_id} not found")
        
        # Get scheduled actions for this round
        scheduled_actions = storage.get_scheduled_actions(simulation_id, round_number)
        print(f"📋 Actions scheduled for round {round_number}: {len(scheduled_actions)}")
        
        if not scheduled_actions:
            print("⚠️  No actions scheduled for this round")
            return self._generate_empty_round(sim, round_number)
        
        # Get active multi-round actions (for context)
        active_actions = storage.get_active_actions(simulation_id)
        print(f"⏳ Active multi-round actions: {len(active_actions)}")
        
        # Get previous actor states to build my_actions history
        prev_actor_states = {}
        if round_number > 0:
            prev_round = round_number - 1
            if str(prev_round) in sim.get('actor_states', {}):
                prev_actor_states = sim['actor_states'][str(prev_round)]
        
        # Build prompt
        prompt = self._build_prompt(sim, scheduled_actions, round_number)
        
        # Retry loop for LLM calls
        print("🤖 Calling world engine LLM...")
        last_error = None
        world_update = None
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": WORLD_ENGINE_SYSTEM},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=32000,  # Increased to prevent truncation
                    temperature=0.8,
                )
                
                response_text = response.choices[0].message.content
                print(f"✅ World engine response received ({len(response_text)} chars)")
                
                # Extract and validate JSON
                world_update = self._extract_json(response_text)
                self._validate_world_update(world_update, scheduled_actions)
                
                # Success! Break out of retry loop
                break
                
            except (ValueError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                print(f"⚠️  Attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2)  # Longer delay for world engine
                continue
        
        # If all retries failed, raise the last error
        if world_update is None:
            print(f"❌ All {MAX_RETRIES} attempts failed for world engine")
            raise last_error
        
        # Get messages for this round (sent by actors in previous round)
        pending_messages = storage.get_messages_for_round(simulation_id, round_number)
        
        # Convert to storage format with my_actions history
        round_data, actor_states = self._convert_to_storage_format(
            world_update, round_number, sim, scheduled_actions, prev_actor_states, pending_messages
        )
        
        # Clear delivered messages
        if pending_messages:
            storage.clear_delivered_messages(simulation_id, round_number)
            print(f"📬 Delivered {len(pending_messages)} message(s) to actors")
        
        # Update action statuses in queue
        for action_result in world_update['action_results']:
            actor_id = action_result['actor_id']
            outcome_dict = {
                'outcome': action_result['outcome'],
                'outcome_quality': action_result.get('outcome_quality', 'modest'),
                'explanation': action_result.get('explanation', '')
            }
            storage.update_scheduled_action_status(
                simulation_id, round_number, actor_id, 
                "completed", outcome_dict
            )
        
        # Handle multi-round actions
        for action in scheduled_actions:
            if action['duration'] > 1:
                # This is a multi-round action, add to active_actions
                active_action = {
                    "actor_id": action['actor_id'],
                    "action": action['action'],
                    "reasoning": action['reasoning'],
                    "started_round": round_number,
                    "duration": action['duration'],
                    "completes_round": round_number + action['duration'],
                    "random_seed": action['random_seed'],
                    "status": "in_progress"
                }
                storage.add_active_action(simulation_id, active_action)
                print(f"➕ Added multi-round action for {action['actor_id']} (completes round {active_action['completes_round']})")
        
        # Check for completing multi-round actions
        for active in active_actions:
            if active['completes_round'] == round_number:
                storage.complete_active_action(
                    simulation_id, active['actor_id'], active['started_round']
                )
                print(f"✅ Completed multi-round action for {active['actor_id']}")
        
        print(f"✅ Round {round_number} processed")
        print(f"   Continue: {round_data['continue_simulation']}")
        
        return {
            "round_data": round_data,
            "actor_states": actor_states
        }
    
    def _build_prompt(self, sim: Dict, scheduled_actions: List[Dict], 
                     round_number: int) -> str:
        """Build the prompt for the world engine."""
        # Build actors summary (public info only)
        actors_summary = []
        for actor in sim['actors']:
            actors_summary.append(
                f"- {actor['identifier']} ({actor['granularity']}): {actor['role_in_simulation']}"
            )
        
        # Build actions list (world engine doesn't see reasoning!)
        actions_list = []
        for action in scheduled_actions:
            actor_identifier = self._get_actor_identifier(sim, action['actor_id'])
            actions_list.append({
                "actor_id": action['actor_id'],
                "actor_identifier": actor_identifier,
                "action": action['action'],
                "duration": action['duration'],
                "random_seed": action['random_seed']
            })
        
        # Get previous round summary if exists
        previous_round_summary = ""
        if sim.get('rounds'):
            last_round = sim['rounds'][-1]
            previous_round_summary = f"\n\nPREVIOUS ROUND:\n{last_round['world_state_summary']}"
        
        prompt = WORLD_ENGINE_USER.format(
            question=sim['question'],
            time_unit=sim['time_unit'],
            current_time=round_number,
            total_duration=sim['simulation_duration'],
            actors_summary='\n'.join(actors_summary),
            actions=json.dumps(actions_list, indent=2)
        )
        
        if previous_round_summary:
            prompt += previous_round_summary
        
        return prompt
    
    def _get_actor_identifier(self, sim: Dict, actor_id: str) -> str:
        """Get actor identifier from actor_id."""
        for actor in sim['actors']:
            if actor['actor_id'] == actor_id:
                return actor['identifier']
        return "Unknown"
    
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
                raise ValueError("No JSON found in world engine response")
            
            json_str = text[start:end+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {json_str[:200]}...")
            print(f"Error at position {e.pos}: {e.msg}")
            
            # Try to fix common JSON issues
            try:
                fixed_json = json_str
                
                # Remove trailing commas
                fixed_json = fixed_json.replace(',]', ']').replace(',}', '}')
                
                # Fix missing commas between fields (common LLM error)
                # Pattern: "field1": value\n  "field2" -> "field1": value,\n  "field2"
                # Add comma after }\n" pattern
                fixed_json = re.sub(r'\}\s*\n\s*"', '},\n  "', fixed_json)
                # Add comma after ]\n" pattern  
                fixed_json = re.sub(r'\]\s*\n\s*"', '],\n  "', fixed_json)
                # Add comma after string value\n" pattern
                fixed_json = re.sub(r'"\s*\n\s*"([^"]+)":\s*', '",\n  "\\1": ', fixed_json)
                
                # Try to add missing closing braces if truncated
                open_braces = fixed_json.count('{') - fixed_json.count('}')
                open_brackets = fixed_json.count('[') - fixed_json.count(']')
                if open_braces > 0:
                    fixed_json += '}' * open_braces
                if open_brackets > 0:
                    fixed_json += ']' * open_brackets
                
                result = json.loads(fixed_json)
                print("✅ Fixed JSON automatically")
                return result
            except Exception as fix_error:
                print(f"⚠️  Auto-fix failed: {fix_error}")
                pass
            
            raise ValueError(f"Invalid JSON in world engine response: {e}")
    
    def _validate_world_update(self, update: Dict, scheduled_actions: List[Dict]) -> None:
        """Validate the world update structure."""
        required_fields = [
            'world_state_update', 'action_results', 'actor_updates',
            'continue_simulation', 'continuation_reasoning'
        ]
        
        for field in required_fields:
            if field not in update:
                raise ValueError(f"Missing required field in world update: {field}")
        
        # Validate we have results for all actions
        action_actor_ids = {a['actor_id'] for a in scheduled_actions}
        result_actor_ids = {r['actor_id'] for r in update['action_results']}
        
        if action_actor_ids != result_actor_ids:
            print(f"⚠️  Warning: Action/result mismatch. Actions: {action_actor_ids}, Results: {result_actor_ids}")
    
    def _convert_to_storage_format(self, world_update: Dict, round_number: int,
                                   sim: Dict, scheduled_actions: List[Dict],
                                   prev_actor_states: Dict, pending_messages: List[Dict] = None) -> tuple:
        """Convert world engine output to storage format with my_actions history."""
        # Public round data
        round_data = {
            "round_number": round_number,
            "world_state_summary": world_update['world_state_update'].get('summary', ''),
            "key_changes": world_update['world_state_update'].get('key_changes', []),
            "emergent_developments": world_update['world_state_update'].get('emergent_developments', []),
            "action_results": world_update['action_results'],
            "continue_simulation": world_update['continue_simulation'],
            "continuation_reasoning": world_update.get('continuation_reasoning', ''),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Build my_actions for each actor
        action_items_by_actor = {}
        for scheduled in scheduled_actions:
            actor_id = scheduled['actor_id']
            
            # Find the result for this action
            result = next(
                (r for r in world_update['action_results'] if r['actor_id'] == actor_id),
                None
            )
            
            action_item = {
                "action": scheduled['action'],
                "reasoning": scheduled['reasoning'],
                "scheduled_round": round_number,
                "duration": scheduled['duration'],
                "status": "completed",
                "outcome": result['outcome'] if result else "UNKNOWN",
                "outcome_quality": result.get('outcome_quality', 'modest') if result else None,
                "outcome_explanation": result.get('explanation', '') if result else None,
                "random_seed": scheduled['random_seed']
            }
            action_items_by_actor[actor_id] = action_item
        
        # Private actor states (keyed by actor_id)
        actor_states = {}
        for update in world_update['actor_updates']:
            actor_id = update['actor_id']
            
            # Get previous my_actions history
            prev_actions = []
            if actor_id in prev_actor_states:
                prev_actions = prev_actor_states[actor_id].get('my_actions', [])
            
            # Add this round's action to history
            my_actions = prev_actions.copy()
            if actor_id in action_items_by_actor:
                my_actions.append(action_items_by_actor[actor_id])
            
            # Handle state_changes - could be dict or string
            state_changes = update.get('state_changes', {})
            if not isinstance(state_changes, dict):
                state_changes = {}
            
            # Get messages for this actor
            actor_messages = []
            if pending_messages:
                actor_messages = [
                    {
                        "from_actor_id": msg['from_actor_id'],
                        "from_actor_identifier": msg.get('from_actor_identifier', ''),
                        "content": msg['content'],
                        "sent_round": msg['sent_round']
                    }
                    for msg in pending_messages
                    if msg['to_actor_id'] == actor_id
                ]
            
            actor_states[actor_id] = {
                "actor_id": actor_id,
                "round_number": round_number,
                "observations": update.get('observations', ''),
                "world_state_summary": world_update['world_state_update'].get('summary', ''),
                "available_actions": state_changes.get('enabled_actions', []),
                "disabled_actions": state_changes.get('disabled_actions', []),
                "resources": state_changes.get('resources', {}),
                "constraints": state_changes.get('constraints', []),
                "messages_received": actor_messages,
                "my_actions": my_actions,
                "direct_impacts": update.get('direct_impacts', ''),
                "indirect_impacts": update.get('indirect_impacts', '')
            }
        
        return round_data, actor_states
    
    def _generate_empty_round(self, sim: Dict, round_number: int) -> Dict[str, Any]:
        """Generate an empty round when no actions are scheduled."""
        round_data = {
            "round_number": round_number,
            "world_state_summary": "No actions occurred this round.",
            "key_changes": [],
            "emergent_developments": [],
            "action_results": [],
            "continue_simulation": True,
            "continuation_reasoning": "Waiting for actor decisions.",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Maintain actor states from previous round
        actor_states = {}
        if round_number > 0:
            prev_round = round_number - 1
            if str(prev_round) in sim.get('actor_states', {}):
                actor_states = sim['actor_states'][str(prev_round)].copy()
        
        return {
            "round_data": round_data,
            "actor_states": actor_states
        }
