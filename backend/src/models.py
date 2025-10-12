"""Data models for the world simulation system."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid


# ============================================================================
# BASE ACTOR MODEL (Static Info)
# ============================================================================

class Actor(BaseModel):
    """Base actor model with static information."""
    actor_id: str = None  # Unique ID assigned at creation
    identifier: str
    research_query: str
    granularity: str
    scale_notes: str
    role_in_simulation: str
    key_interactions: List[str]
    
    # Enrichment fields (added after enrichment)
    memory: Optional[str] = None
    intrinsic_characteristics: Optional[str] = None
    predispositions: Optional[str] = None
    enriched: Optional[bool] = False
    
    def __init__(self, **data):
        if 'actor_id' not in data or data['actor_id'] is None:
            data['actor_id'] = str(uuid.uuid4())
        super().__init__(**data)


# ============================================================================
# ACTION (in actor's queue)
# ============================================================================

class ActorActionItem(BaseModel):
    """An action in an actor's queue."""
    action: str
    reasoning: str  # Private reasoning
    scheduled_round: int  # When this executes
    duration: int  # How many rounds it takes
    status: str  # "queued", "executing", "completed", "cancelled"
    outcome: Optional[str] = None  # "SUCCESS" or "FAILURE" (filled after execution)
    outcome_quality: Optional[str] = None  # "strong", "modest", "weak", "catastrophic"
    outcome_explanation: Optional[str] = None
    random_seed: Optional[float] = None  # Assigned when action is processed


# ============================================================================
# ACTOR STATE (Dynamic, changes each turn)
# ============================================================================

class ActorState(BaseModel):
    """Dynamic state of an actor during simulation."""
    actor_id: str
    round_number: int
    
    # What the actor can observe
    world_state_summary: str
    observations: str
    
    # Actor's current capabilities
    available_actions: List[str] = []
    disabled_actions: List[str] = []
    resources: Dict[str, Any] = {}
    constraints: List[str] = []
    
    # Communication
    messages_received: List[Dict[str, str]] = []
    
    # Actor's action history and plans (replaces prev_action/prev_reasoning)
    my_actions: List[ActorActionItem] = []
    
    # Impacts from world
    direct_impacts: Optional[str] = None
    indirect_impacts: Optional[str] = None


# ============================================================================
# ACTOR ACTION (What actor decides to do)
# ============================================================================

class ActorAction(BaseModel):
    """Action decision submitted by an actor."""
    actor_id: str
    action: str  # Concise action description (≤100 chars)
    reasoning: str  # Private reasoning
    execute_round: int  # Which round to execute this action
    duration: int = 1  # How many rounds it takes (default 1)
    random_seed: Optional[float] = None  # Auto-assigned if not provided


# ============================================================================
# ACTION RESULT (From world engine)
# ============================================================================

class ActionResult(BaseModel):
    """Result of an action after world engine processing."""
    actor_id: str
    action: str
    success_threshold: float  # Threshold for success (0-1)
    random_seed: float  # The random seed used
    outcome: str  # "SUCCESS" or "FAILURE"
    outcome_quality: str  # "strong", "modest", "weak", "catastrophic"
    explanation: str  # Why this outcome occurred


# ============================================================================
# ROUND (Public Transcript Entry)
# ============================================================================

class Round(BaseModel):
    """Public information for a single round."""
    round_number: int
    world_state_summary: str
    key_changes: List[str]
    emergent_developments: List[str]
    action_results: List[ActionResult]
    continue_simulation: bool
    continuation_reasoning: Optional[str] = None
    timestamp: str


# ============================================================================
# SCHEDULED ACTION (in the queue)
# ============================================================================

class ScheduledAction(BaseModel):
    """An action scheduled to execute in a future round."""
    actor_id: str
    action: str
    reasoning: str  # Private
    scheduled_round: int  # When it executes
    duration: int  # How many rounds it takes
    random_seed: float
    scheduled_at_round: int  # When it was scheduled
    status: str  # "pending", "executing", "completed", "cancelled"


# ============================================================================
# ACTIVE ACTION (multi-round action in progress)
# ============================================================================

class ActiveAction(BaseModel):
    """A multi-round action currently executing."""
    actor_id: str
    action: str
    reasoning: str
    started_round: int
    duration: int
    completes_round: int  # started_round + duration
    random_seed: float
    status: str  # "in_progress"


# ============================================================================
# SIMULATION (Everything Embedded)
# ============================================================================

class Simulation(BaseModel):
    """
    Complete simulation document (stored in MongoDB).
    
    MongoDB Schema:
    {
      simulation_id: string,
      question: string,
      time_unit: string,
      simulation_duration: int,
      current_round: int,
      status: string,
      created_at: string,
      updated_at: string,
      
      actors: [
        {
          actor_id: string,
          identifier: string,
          research_query: string,
          granularity: string,
          scale_notes: string,
          role_in_simulation: string,
          key_interactions: [string],
          enriched: boolean,
          memory?: string,
          intrinsic_characteristics?: string,
          predispositions?: string
        }
      ],
      
      rounds: [
        {
          round_number: int,
          world_state_summary: string,
          key_changes: [string],
          emergent_developments: [string],
          action_results: [
            {
              actor_id: string,
              action: string,
              success_threshold: float,
              random_seed: float,
              outcome: "SUCCESS" | "FAILURE",
              outcome_quality: string,
              explanation: string
            }
          ],
          continue_simulation: boolean,
          continuation_reasoning: string,
          timestamp: string
        }
      ],
      
      actor_states: {
        "0": {
          "actor_id": {
            actor_id: string,
            round_number: int,
            world_state_summary: string,
            observations: string,
            available_actions: [string],
            disabled_actions: [string],
            resources: {},
            constraints: [string],
            messages_received: [{}],
            my_actions: [
              {
                action: string,
                reasoning: string,
                scheduled_round: int,
                duration: int,
                status: string,
                outcome?: string,
                outcome_quality?: string,
                outcome_explanation?: string,
                random_seed?: float
              }
            ],
            direct_impacts: string,
            indirect_impacts: string
          }
        }
      },
      
      action_schedule: {
        "0": [
          {
            actor_id: string,
            action: string,
            reasoning: string,
            scheduled_round: int,
            duration: int,
            random_seed: float,
            scheduled_at_round: int,
            status: "pending" | "executing" | "completed" | "cancelled"
          }
        ]
      },
      
      active_actions: [
        {
          actor_id: string,
          action: string,
          reasoning: string,
          started_round: int,
          duration: int,
          completes_round: int,
          random_seed: float,
          status: "in_progress"
        }
      ],
      
      active_actor_ids: [string],
      eliminated_actor_ids: [string]
    }
    """
    # Core metadata
    simulation_id: str
    question: str
    time_unit: str
    simulation_duration: int
    current_round: int = 0
    status: str  # "created", "enriching", "enriched", "running", "completed"
    created_at: str
    updated_at: str
    
    # Collections
    actors: List[Dict[str, Any]]  # Actor profiles with enrichment
    rounds: List[Dict[str, Any]] = []  # Public transcript (Round objects)
    actor_states: Dict[str, Dict[str, Dict[str, Any]]] = {}  # Round -> Actor ID -> ActorState
    action_schedule: Dict[str, List[Dict[str, Any]]] = {}  # Round -> [ScheduledAction]
    active_actions: List[Dict[str, Any]] = []  # [ActiveAction]
    
    # Actor tracking
    active_actor_ids: List[str] = []
    eliminated_actor_ids: List[str] = []
    
    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# WORLD UPDATE (From world engine, converted to Round)
# ============================================================================

class WorldUpdate(BaseModel):
    """World engine output (gets converted to Round + ActorStates)."""
    round_number: int
    world_state_summary: str
    key_changes: List[str]
    emergent_developments: List[str]
    action_results: List[ActionResult]
    actor_updates: List[ActorState]
    continue_simulation: bool
    continuation_reasoning: str


# ============================================================================
# REQUEST/RESPONSE MODELS FOR API
# ============================================================================

class ActorGenerationRequest(BaseModel):
    """Request to generate actors."""
    question: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "How will remote work affect tech companies?"
            }
        }


class SimulationResponse(BaseModel):
    """Response containing simulation data (public info only)."""
    simulation_id: str
    question: str
    time_unit: str
    simulation_duration: int
    status: str
    current_round: int
    actors: List[Actor]  # Without private state
    rounds: List[Round] = []  # Public transcript


class EnrichmentProgress(BaseModel):
    """Progress update during enrichment."""
    simulation_id: str
    status: str
    enriched_count: int
    total_count: int
    current_actor: Optional[str] = None

