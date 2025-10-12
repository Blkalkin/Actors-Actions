"""MongoDB storage for simulations."""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid
import ssl
import certifi

from src.config import MONGODB_URI, MONGODB_DATABASE


class SimulationStorage:
    """Handles MongoDB storage for simulations."""
    
    def __init__(self):
        """Initialize MongoDB connection."""
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI not set in environment variables")
        
        # Use certifi's certificate bundle for SSL verification (fixes macOS issues)
        self.client = MongoClient(
            MONGODB_URI,
            tlsCAFile=certifi.where()
        )
        self.db = self.client[MONGODB_DATABASE]
        self.simulations = self.db.simulations
        
        # Create indexes
        self.simulations.create_index("simulation_id", unique=True)
        self.simulations.create_index("created_at")
        
        # Test connection
        try:
            self.client.admin.command('ping')
            print("✅ Connected to MongoDB")
        except ConnectionFailure:
            print("❌ MongoDB connection failed")
            raise
    
    def create_simulation(self, question: str, time_unit: str, 
                         simulation_duration: int, actors: List[Dict]) -> str:
        """
        Create a new simulation.
        
        Actors must have actor_id already assigned.
        
        Returns:
            simulation_id: Unique ID for this simulation
        """
        simulation_id = str(uuid.uuid4())
        
        # Extract active actor IDs
        active_actor_ids = [actor['actor_id'] for actor in actors]
        
        document = {
            "simulation_id": simulation_id,
            "question": question,
            "time_unit": time_unit,
            "simulation_duration": simulation_duration,
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "current_round": 0,
            "actors": actors,
            "rounds": [],
            "actor_states": {},
            "action_schedule": {},  # Round number -> list of scheduled actions
            "active_actions": [],  # Multi-round actions in progress
            "active_actor_ids": active_actor_ids,
            "eliminated_actor_ids": []
        }
        
        self.simulations.insert_one(document)
        print(f"💾 Created simulation: {simulation_id}")
        
        return simulation_id
    
    def get_simulation(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Get a simulation by ID."""
        return self.simulations.find_one(
            {"simulation_id": simulation_id},
            {"_id": 0}  # Exclude MongoDB's _id field
        )
    
    def list_simulations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent simulations."""
        return list(self.simulations.find(
            {},
            {"_id": 0, "actors": 0, "transcript": 0}  # Exclude large fields
        ).sort("created_at", -1).limit(limit))
    
    def update_simulation_status(self, simulation_id: str, status: str) -> None:
        """Update simulation status."""
        self.simulations.update_one(
            {"simulation_id": simulation_id},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    def enrich_actor(self, simulation_id: str, actor_id: str,
                    memory: str, characteristics: str, predispositions: str) -> None:
        """Add enrichment data to an actor using actor_id."""
        self.simulations.update_one(
            {
                "simulation_id": simulation_id,
                "actors.actor_id": actor_id
            },
            {
                "$set": {
                    "actors.$.memory": memory,
                    "actors.$.intrinsic_characteristics": characteristics,
                    "actors.$.predispositions": predispositions,
                    "actors.$.enriched": True,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
    
    def add_round(self, simulation_id: str, round_data: Dict, 
                  actor_states: Dict[str, Dict]) -> None:
        """
        Add a round to the simulation.
        
        Args:
            simulation_id: The simulation ID
            round_data: Public round data (Round model)
            actor_states: Dict of actor states keyed by actor_id
        """
        round_number = round_data['round_number']
        
        self.simulations.update_one(
            {"simulation_id": simulation_id},
            {
                "$push": {"rounds": round_data},
                "$set": {
                    f"actor_states.{round_number}": actor_states,
                    "current_round": round_number,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
    
    def update_actor_state(self, simulation_id: str, actor_id: str, 
                          round_number: int, state_update: Dict) -> None:
        """Update a specific actor's state for a round."""
        self.simulations.update_one(
            {"simulation_id": simulation_id},
            {
                "$set": {
                    f"actor_states.{round_number}.{actor_id}": state_update,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
    
    def get_rounds(self, simulation_id: str) -> List[Dict]:
        """Get all public rounds for a simulation."""
        sim = self.simulations.find_one(
            {"simulation_id": simulation_id},
            {"_id": 0, "rounds": 1}
        )
        return sim.get("rounds", []) if sim else []
    
    def get_actor_state(self, simulation_id: str, actor_id: str, round_number: int) -> Optional[Dict]:
        """Get a specific actor's state for a specific round."""
        sim = self.simulations.find_one(
            {"simulation_id": simulation_id},
            {"_id": 0, f"actor_states.{round_number}.{actor_id}": 1}
        )
        if sim and "actor_states" in sim:
            return sim["actor_states"].get(str(round_number), {}).get(actor_id)
        return None
    
    def get_actors(self, simulation_id: str) -> List[Dict]:
        """Get all actors for a simulation."""
        sim = self.simulations.find_one(
            {"simulation_id": simulation_id},
            {"_id": 0, "actors": 1}
        )
        return sim.get("actors", []) if sim else []
    
    def delete_simulation(self, simulation_id: str) -> bool:
        """Delete a simulation."""
        result = self.simulations.delete_one({"simulation_id": simulation_id})
        return result.deleted_count > 0
    
    # =========================================================================
    # ACTION SCHEDULING METHODS
    # =========================================================================
    
    def schedule_action(self, simulation_id: str, scheduled_action: Dict) -> None:
        """
        Schedule an action to execute in a future round.
        
        Args:
            simulation_id: The simulation ID
            scheduled_action: ScheduledAction dict with execute_round specified
        """
        execute_round = str(scheduled_action['scheduled_round'])
        
        self.simulations.update_one(
            {"simulation_id": simulation_id},
            {
                "$push": {f"action_schedule.{execute_round}": scheduled_action},
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            }
        )
    
    def get_scheduled_actions(self, simulation_id: str, round_number: int) -> List[Dict]:
        """Get all actions scheduled for a specific round."""
        sim = self.simulations.find_one(
            {"simulation_id": simulation_id},
            {"_id": 0, f"action_schedule.{round_number}": 1}
        )
        if sim and "action_schedule" in sim:
            return sim["action_schedule"].get(str(round_number), [])
        return []
    
    def update_scheduled_action_status(self, simulation_id: str, round_number: int,
                                      actor_id: str, status: str,
                                      outcome: Optional[Dict] = None) -> None:
        """
        Update the status of a scheduled action.
        
        Args:
            simulation_id: The simulation ID
            round_number: Round where action is scheduled
            actor_id: Actor who owns the action
            status: New status ("executing", "completed", "cancelled")
            outcome: Optional outcome dict with result details
        """
        # Get current scheduled actions for this round
        actions = self.get_scheduled_actions(simulation_id, round_number)
        
        # Find and update the action
        for i, action in enumerate(actions):
            if action['actor_id'] == actor_id:
                actions[i]['status'] = status
                if outcome:
                    actions[i]['outcome'] = outcome.get('outcome')
                    actions[i]['outcome_quality'] = outcome.get('outcome_quality')
                    actions[i]['outcome_explanation'] = outcome.get('explanation')
                break
        
        # Update in database
        self.simulations.update_one(
            {"simulation_id": simulation_id},
            {
                "$set": {
                    f"action_schedule.{round_number}": actions,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
    
    def add_active_action(self, simulation_id: str, active_action: Dict) -> None:
        """Add a multi-round action to the active actions list."""
        self.simulations.update_one(
            {"simulation_id": simulation_id},
            {
                "$push": {"active_actions": active_action},
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            }
        )
    
    def get_active_actions(self, simulation_id: str) -> List[Dict]:
        """Get all currently active multi-round actions."""
        sim = self.simulations.find_one(
            {"simulation_id": simulation_id},
            {"_id": 0, "active_actions": 1}
        )
        return sim.get("active_actions", []) if sim else []
    
    def complete_active_action(self, simulation_id: str, actor_id: str, 
                              started_round: int) -> None:
        """Remove a completed action from active_actions."""
        self.simulations.update_one(
            {"simulation_id": simulation_id},
            {
                "$pull": {
                    "active_actions": {
                        "actor_id": actor_id,
                        "started_round": started_round
                    }
                },
                "$set": {"updated_at": datetime.utcnow().isoformat()}
            }
        )
    
    def cancel_scheduled_action(self, simulation_id: str, round_number: int,
                                actor_id: str) -> None:
        """Cancel a scheduled action before it executes."""
        self.update_scheduled_action_status(
            simulation_id, round_number, actor_id, "cancelled"
        )


# Global storage instance
_storage = None

def get_storage() -> SimulationStorage:
    """Get or create the global storage instance."""
    global _storage
    if _storage is None:
        _storage = SimulationStorage()
    return _storage

