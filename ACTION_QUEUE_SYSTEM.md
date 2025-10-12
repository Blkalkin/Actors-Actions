# Action Queue System Documentation

> **Note:** This document provides a deep dive into action scheduling patterns. For general backend architecture, see [BACKEND_DESIGN.md](BACKEND_DESIGN.md).

## Overview

The Action Queue System enables sophisticated multi-round action planning where actors can:
- Schedule actions for current or future rounds
- Plan multi-round actions that span multiple time periods
- Update their plans each round
- Track their full action history with outcomes and private reasoning

## Core Concepts

### 1. Action Scheduling

Actions are not executed immediately but placed in a queue by round number:

```javascript
action_schedule: {
  "0": [action1, action2],  // Execute in round 0
  "3": [action3],           // Execute in round 3
  "5": [action4, action5]   // Execute in round 5
}
```

### 2. Multi-Round Actions

Actions can have `duration > 1`, meaning they:
- Start executing in `execute_round`
- Continue for `duration` rounds
- Complete in `execute_round + duration`
- Are tracked in `active_actions` while in progress

### 3. Action Updates

Each round, actors get a chance to:
- Update queued actions (before they execute)
- Cancel scheduled actions
- Schedule new actions
- Change their strategy based on observations

### 4. Actor Action History

Each actor's state includes `my_actions` - a complete history:

```javascript
my_actions: [
  {
    action: "Launch PR campaign",
    reasoning: "Need immediate damage control",  // Private
    scheduled_round: 0,
    duration: 1,
    status: "completed",
    outcome: "SUCCESS",
    outcome_quality: "modest",
    outcome_explanation: "Campaign reached target audience...",
    random_seed: 0.73
  },
  {
    action: "Open new office",
    reasoning: "Expand to new market",
    scheduled_round: 5,
    duration: 3,
    status: "queued",
    outcome: null,
    random_seed: 0.82
  }
]
```

## Data Structures

### ActorActionItem (in my_actions)

```python
class ActorActionItem(BaseModel):
    action: str                      # What they did/will do
    reasoning: str                   # Private reasoning
    scheduled_round: int             # When it executes
    duration: int                    # How many rounds
    status: str                      # "queued", "executing", "completed", "cancelled"
    outcome: Optional[str]           # "SUCCESS" or "FAILURE"
    outcome_quality: Optional[str]   # "strong", "modest", "weak", "catastrophic"
    outcome_explanation: Optional[str]
    random_seed: Optional[float]
```

### ScheduledAction (in action_schedule)

```python
class ScheduledAction(BaseModel):
    actor_id: str
    action: str
    reasoning: str                   # Private
    scheduled_round: int             # When it executes
    duration: int
    random_seed: float
    scheduled_at_round: int          # When it was scheduled
    status: str                      # "pending", "executing", "completed", "cancelled"
```

### ActiveAction (in active_actions)

```python
class ActiveAction(BaseModel):
    actor_id: str
    action: str
    reasoning: str
    started_round: int
    duration: int
    completes_round: int             # started_round + duration
    random_seed: float
    status: str                      # "in_progress"
```

### ActorState (per round, per actor)

```python
class ActorState(BaseModel):
    actor_id: str
    round_number: int
    
    # Observations
    world_state_summary: str
    observations: str
    
    # Capabilities
    available_actions: List[str]
    disabled_actions: List[str]
    resources: Dict[str, Any]
    constraints: List[str]
    
    # Communication
    messages_received: List[Dict[str, str]]
    
    # Action history (REPLACES prev_action/prev_reasoning)
    my_actions: List[ActorActionItem]
    
    # Impacts
    direct_impacts: Optional[str]
    indirect_impacts: Optional[str]
```

## API Workflow

### Creating and Scheduling Actions

```bash
# 1. Generate action using AI
POST /api/simulations/{id}/actors/{actor_id}/generate-action
Response: {
  "action": "Launch PR campaign",
  "reasoning": "Need immediate damage control",
  "execute_round": 0,
  "duration": 1
}

# 2. Schedule the action
POST /api/simulations/{id}/schedule-action
Body: {
  "actor_id": "uuid-1",
  "action": "Launch PR campaign",
  "reasoning": "Need immediate damage control",
  "execute_round": 0,
  "duration": 1
}

# 3. Process the round
POST /api/simulations/{id}/process-round
# World engine executes all actions scheduled for current round
```

### Checking Actor State

```bash
# Get actor's current state (includes my_actions history)
GET /api/simulations/{id}/actors/{actor_id}/state

Response: {
  "actor_id": "uuid-1",
  "round_number": 3,
  "observations": "...",
  "my_actions": [
    {
      "action": "Launch PR campaign",
      "reasoning": "Need immediate damage control",
      "scheduled_round": 0,
      "duration": 1,
      "status": "completed",
      "outcome": "SUCCESS",
      "outcome_quality": "modest",
      "outcome_explanation": "..."
    },
    {
      "action": "Announce restructuring",
      "reasoning": "Follow up on PR success",
      "scheduled_round": 1,
      "duration": 1,
      "status": "completed",
      "outcome": "FAILURE",
      "outcome_quality": "weak",
      "outcome_explanation": "..."
    },
    {
      "action": "Open new office",
      "reasoning": "Expand despite setback",
      "scheduled_round": 5,
      "duration": 3,
      "status": "queued",
      "outcome": null
    }
  ],
  "direct_impacts": "...",
  "indirect_impacts": "..."
}
```

### Viewing Scheduled Actions

```bash
# See what's queued for a specific round
GET /api/simulations/{id}/scheduled-actions/5

Response: {
  "simulation_id": "sim-123",
  "round_number": 5,
  "actions": [
    {
      "actor_id": "uuid-1",
      "action": "Open new office",
      "scheduled_round": 5,
      "duration": 3,
      "status": "pending",
      "scheduled_at_round": 2
    },
    {
      "actor_id": "uuid-2",
      "action": "File lawsuit",
      "scheduled_round": 5,
      "duration": 1,
      "status": "pending",
      "scheduled_at_round": 4
    }
  ]
}
```

## World Engine Flow

```python
def process_round(simulation_id: str, round_number: int):
    # 1. Get scheduled actions for this round
    scheduled_actions = storage.get_scheduled_actions(simulation_id, round_number)
    
    # 2. Get active multi-round actions (for context)
    active_actions = storage.get_active_actions(simulation_id)
    
    # 3. Build prompt with world state + actions
    prompt = build_prompt(sim, scheduled_actions, round_number)
    
    # 4. Call LLM to process actions
    world_update = llm.process(prompt)
    
    # 5. Update action statuses in queue
    for result in world_update['action_results']:
        storage.update_scheduled_action_status(
            simulation_id, round_number, result['actor_id'],
            "completed", outcome_dict
        )
    
    # 6. Handle multi-round actions
    for action in scheduled_actions:
        if action['duration'] > 1:
            # Add to active_actions
            storage.add_active_action(simulation_id, active_action)
    
    # 7. Check for completing multi-round actions
    for active in active_actions:
        if active['completes_round'] == round_number:
            storage.complete_active_action(simulation_id, active['actor_id'])
    
    # 8. Build actor states with my_actions history
    actor_states = build_actor_states(world_update, scheduled_actions, prev_states)
    
    # 9. Store round and states
    storage.add_round(simulation_id, round_data, actor_states)
```

## Benefits

### ✅ Clear Execution Model
- Queue makes it explicit when actions execute
- No ambiguity about action timing

### ✅ Strategic Planning
- Actors can schedule future actions
- Can coordinate timing across actors

### ✅ Easy Updates
- Actors can change their minds before execution
- Cancel or reschedule queued actions

### ✅ Full Context
- Actors see their entire action history
- Can reference past reasoning and outcomes

### ✅ Multi-Round Actions
- Model actions that take time
- Track in-progress actions
- Complete them appropriately

### ✅ Information Asymmetry
- Reasoning is private (stored with action)
- World engine only sees observable actions
- Actors can strategize privately

## Storage Methods

### Scheduling
- `schedule_action(simulation_id, scheduled_action)` - Add to queue
- `get_scheduled_actions(simulation_id, round_number)` - Get actions for round
- `update_scheduled_action_status(...)` - Update status/outcome
- `cancel_scheduled_action(...)` - Cancel before execution

### Multi-Round Tracking
- `add_active_action(simulation_id, active_action)` - Start tracking
- `get_active_actions(simulation_id)` - Get all in-progress actions
- `complete_active_action(simulation_id, actor_id, started_round)` - Remove completed

### State Access
- `get_actor_state(simulation_id, actor_id, round_number)` - Get actor's state
- `update_actor_state(simulation_id, actor_id, round_number, state)` - Update state

## Example Scenario

### Round 0
```
TechCorp CEO schedules:
  - Round 0: "Announce product delay" (duration: 1)
  - Round 2: "Launch revised product" (duration: 2)

World Engine processes Round 0:
  → CEO announces delay
  → Outcome: SUCCESS (modest)
  → Competitors observe, media reacts
```

### Round 1
```
TechCorp CEO sees:
  - my_actions[0]: "Announce delay" - SUCCESS (modest)
  - "Competitors are accelerating their timelines"
  
CEO updates plan:
  - Cancels Round 2 launch
  - Schedules Round 3: "Form strategic partnership" (duration: 3)
```

### Round 2
```
No action scheduled for TechCorp CEO
World Engine: "CEO remains quiet this round"
```

### Round 3
```
World Engine processes:
  - CEO: "Form strategic partnership" (starts, duration: 3)
  → Added to active_actions (completes_round: 6)
  → Status: "in_progress"
```

### Round 6
```
Partnership action completes
  → Removed from active_actions
  → Outcome evaluated
  → Added to CEO's my_actions history
```

This system enables complex, strategic, multi-round simulations with full actor agency and adaptability.

