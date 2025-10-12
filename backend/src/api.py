"""FastAPI server for the world simulation system."""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import traceback
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor
import weave
import os

from src.engines.actor_generation import ActorGenerator
from src.engines.actor_enrichment import ActorEnricher
from src.engines.world_engine import WorldEngine
from src.engines.actor_action import ActorActionEngine
from src.storage import get_storage
from src.config import WANDB_API_KEY
from src.models import (
    Actor,
    ActorGenerationRequest,
    SimulationResponse,
    ActorState,
    ActorAction,
    ScheduledAction,
    ActionResult,
    WorldUpdate
)

# Initialize Weave for LLM observability
if WANDB_API_KEY:
    os.environ["WANDB_API_KEY"] = WANDB_API_KEY
    weave.init("actors-actions-simulation")
    print("✅ Weave initialized for LLM observability")
else:
    print("⚠️  WANDB_API_KEY not found - Weave tracing disabled")

app = FastAPI(
    title="Actors-Actions World Simulation API",
    description="API for generating and running LLM-based world simulations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=10)


# ============================================================================
# ASYNC WRAPPERS FOR STORAGE (to prevent blocking event loop)
# ============================================================================

async def async_get_storage():
    """Get storage instance (wrapped for async context)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, get_storage)

async def async_storage_operation(func, *args, **kwargs):
    """Run any storage operation in thread pool to avoid blocking."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Actors-Actions World Simulation API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "create_simulation": "POST /api/simulations/create",
            "get_simulation": "GET /api/simulations/{simulation_id}",
            "list_simulations": "GET /api/simulations",
            "enrich_simulation": "POST /api/simulations/{simulation_id}/enrich",
            "schedule_action": "POST /api/simulations/{simulation_id}/schedule-action",
            "generate_actor_action": "POST /api/simulations/{simulation_id}/actors/{actor_id}/generate-action",
            "get_actor_state": "GET /api/simulations/{simulation_id}/actors/{actor_id}/state",
            "get_scheduled_actions": "GET /api/simulations/{simulation_id}/scheduled-actions/{round_number}",
            "process_round": "POST /api/simulations/{simulation_id}/process-round",
            "get_rounds": "GET /api/simulations/{simulation_id}/rounds",
            "delete_simulation": "DELETE /api/simulations/{simulation_id}",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        storage = get_storage()
        # Test MongoDB connection
        storage.client.admin.command('ping')
        return {"status": "healthy", "mongodb": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/api/simulations/create", response_model=SimulationResponse)
async def create_simulation(request: ActorGenerationRequest):
    """
    Create a new simulation by generating actors.
    
    This endpoint:
    1. Creates a placeholder simulation immediately
    2. Generates actors in the background
    3. Returns the simulation ID right away
    
    Poll the simulation to check when actor generation is complete.
    """
    try:
        if not request.question or request.question.strip() == "":
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        print(f"\n{'='*80}")
        print(f"📥 Creating simulation: {request.question[:80]}...")
        print(f"{'='*80}\n")
        
        # Create placeholder simulation immediately
        storage = get_storage()
        import uuid
        simulation_id = str(uuid.uuid4())
        
        # Create minimal simulation document
        await async_storage_operation(
            storage.create_simulation,
            question=request.question,
            time_unit="unknown",  # Will be updated
            simulation_duration=0,  # Will be updated
            actors=[],  # Will be populated
            simulation_id=simulation_id
        )
        
        # Generate actors in background
        loop = asyncio.get_running_loop()
        loop.run_in_executor(executor, _generate_actors_background, simulation_id, request.question)
        
        print(f"✅ Created simulation {simulation_id} (generating actors...)\n")
        
        return {
            "simulation_id": simulation_id,
            "question": request.question,
            "time_unit": "pending",
            "simulation_duration": 0,
            "status": "generating_actors",
            "current_round": 0,
            "actors": []
        }
        
    except ValueError as e:
        print(f"❌ Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Server error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulations/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(simulation_id: str):
    """Get a simulation by ID."""
    try:
        storage = get_storage()
        simulation = await async_storage_operation(storage.get_simulation, simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        return simulation
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving simulation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulations")
async def list_simulations(limit: int = 20):
    """List recent simulations."""
    try:
        storage = get_storage()
        simulations = await async_storage_operation(storage.list_simulations, limit=limit)
        
        # Add actor count (run in parallel to avoid blocking)
        async def get_actor_count(sim):
            full_sim = await async_storage_operation(storage.get_simulation, sim['simulation_id'])
            sim['actors_count'] = len(full_sim['actors']) if full_sim else 0
            return sim
        
        simulations = await asyncio.gather(*[get_actor_count(sim) for sim in simulations])
        
        return {"simulations": simulations, "count": len(simulations)}
        
    except Exception as e:
        print(f"❌ Error listing simulations: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulations/{simulation_id}/rounds")
async def get_rounds(simulation_id: str):
    """Get the public rounds/transcript for a simulation."""
    try:
        storage = get_storage()
        rounds = await async_storage_operation(storage.get_rounds, simulation_id)
        
        return {"simulation_id": simulation_id, "rounds": rounds}
        
    except Exception as e:
        print(f"❌ Error retrieving rounds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_actors_background(simulation_id: str, question: str):
    """Background task to generate actors."""
    try:
        storage = get_storage()
        
        print(f"🤖 Generating actors for simulation {simulation_id}...")
        
        # Generate actors
        generator = ActorGenerator()
        result = generator.generate(question)
        
        # Update simulation with actors
        storage.update_simulation(
            simulation_id=simulation_id,
            update_data={
                "actors": result['actors'],
                "time_unit": result['time_unit'],
                "simulation_duration": result['simulation_duration'],
                "status": "created"
            }
        )
        
        print(f"✅ Actors generated for simulation {simulation_id}")
        
    except Exception as e:
        print(f"❌ Error generating actors: {e}")
        traceback.print_exc()
        # Update status to failed
        try:
            storage = get_storage()
            storage.update_simulation_status(simulation_id, "failed")
        except:
            pass


def _run_enrichment(simulation_id: str):
    """Background task to enrich actors."""
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            print(f"❌ Simulation {simulation_id} not found")
            return
        
        print(f"\n{'='*80}")
        print(f"🔬 Starting enrichment for simulation: {simulation_id}")
        print(f"   Actors to enrich: {len(simulation['actors'])}")
        print(f"{'='*80}\n")
        
        # Enrich each actor
        enricher = ActorEnricher()
        enriched_count = 0
        total_actors = len(simulation['actors'])
        
        for actor in simulation['actors']:
            try:
                enrichment_data = enricher.enrich(actor)
                
                # Save enrichment to database (use actor_id)
                storage.enrich_actor(
                    simulation_id=simulation_id,
                    actor_id=actor['actor_id'],
                    memory=enrichment_data['memory'],
                    characteristics=enrichment_data['intrinsic_characteristics'],
                    predispositions=enrichment_data['predispositions']
                )
                
                enriched_count += 1
                print(f"   Progress: {enriched_count}/{total_actors}")
                
            except Exception as e:
                print(f"⚠️  Failed to enrich {actor['identifier']}: {e}")
                continue
        
        # Only mark as enriched if ALL actors succeeded
        if enriched_count == total_actors:
            storage.update_simulation_status(simulation_id, "enriched")
            print(f"\n✅ Enrichment complete: {enriched_count}/{total_actors} actors\n")
        else:
            # Reset status to "created" if partial/complete failure
            storage.update_simulation_status(simulation_id, "created")
            print(f"\n⚠️  Partial enrichment: {enriched_count}/{total_actors} actors succeeded")
            print(f"   Status reset to 'created'. Try enriching again.\n")
        
    except Exception as e:
        print(f"❌ Error enriching simulation: {e}")
        traceback.print_exc()
        # Update status to failed
        try:
            storage.update_simulation_status(simulation_id, "created")
        except:
            pass


@app.post("/api/simulations/{simulation_id}/enrich")
async def enrich_simulation(simulation_id: str):
    """
    Enrich all actors in a simulation with detailed profiles.
    
    This calls the enrichment model (Gemini) to research each actor and add:
    - Memory (historical context)
    - Intrinsic characteristics (capabilities, resources, constraints)
    - Predispositions (behavioral patterns, decision-making style)
    
    This runs in the background and returns immediately.
    Poll the simulation status to check when enrichment is complete.
    """
    try:
        storage = get_storage()
        simulation = await async_storage_operation(storage.get_simulation, simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        if simulation.get('status') == 'enriching':
            raise HTTPException(status_code=400, detail="Enrichment already in progress")
        
        if simulation.get('status') == 'enriched':
            return {"message": "Simulation already enriched", "simulation_id": simulation_id}
        
        # Update status to enriching
        await async_storage_operation(storage.update_simulation_status, simulation_id, "enriching")
        
        # Start enrichment in separate thread (don't await, fire and forget)
        loop = asyncio.get_running_loop()
        loop.run_in_executor(executor, _run_enrichment, simulation_id)
        
        # Return immediately
        return {
            "message": "Enrichment started",
            "simulation_id": simulation_id,
            "status": "enriching"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting enrichment: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulations/{simulation_id}/schedule-action")
async def schedule_action(simulation_id: str, action: ActorAction):
    """
    Schedule an action for an actor.
    
    The action will be added to the action queue for the specified execute_round.
    Actors can schedule actions for the current round or future rounds.
    """
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        # Auto-assign random seed if not present
        import random
        if action.random_seed is None:
            action.random_seed = random.random()
        
        # Create scheduled action
        scheduled_action = {
            "actor_id": action.actor_id,
            "action": action.action,
            "reasoning": action.reasoning,
            "scheduled_round": action.execute_round,
            "duration": action.duration,
            "random_seed": action.random_seed,
            "scheduled_at_round": simulation.get('current_round', 0),
            "status": "pending"
        }
        
        # Add to queue
        storage.schedule_action(simulation_id, scheduled_action)
        
        print(f"📅 Action scheduled for {action.actor_id} in round {action.execute_round}")
        
        return {
            "message": "Action scheduled",
            "simulation_id": simulation_id,
            "actor_id": action.actor_id,
            "execute_round": action.execute_round
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error scheduling action: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulations/{simulation_id}/actors/{actor_id}/generate-action")
async def generate_actor_action(simulation_id: str, actor_id: str):
    """
    Generate an action for a specific actor using the Actor Action Engine.
    
    This will:
    1. Get the actor's current state
    2. Call the Actor Action Engine to generate a decision
    3. Return the generated action (not automatically scheduled)
    """
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        # Find actor
        actor = next((a for a in simulation['actors'] if a['actor_id'] == actor_id), None)
        if not actor:
            raise HTTPException(status_code=404, detail="Actor not found")
        
        # Get current actor state
        current_round = simulation.get('current_round', 0)
        actor_state = None
        
        if current_round > 0:
            actor_states_for_round = simulation.get('actor_states', {}).get(str(current_round - 1), {})
            actor_state = actor_states_for_round.get(actor_id, {})
        
        # If no state yet, create initial state
        if not actor_state:
            actor_state = {
                "actor_id": actor_id,
                "round_number": current_round,
                "world_state_summary": "Initial state",
                "observations": "Beginning of simulation",
                "available_actions": [],
                "my_actions": [],
                "resources": {},
                "constraints": [],
                "messages_received": [],
                "direct_impacts": "None yet",
                "indirect_impacts": "None yet"
            }
        
        # Generate action
        action_engine = ActorActionEngine()
        action_decision = action_engine.generate_action(
            actor=actor,
            actor_state=actor_state,
            question=simulation['question'],
            time_unit=simulation['time_unit'],
            current_round=current_round,
            simulation_duration=simulation['simulation_duration']
        )
        
        return {
            "actor_id": actor_id,
            "action_decision": action_decision,
            "message": "Action generated (not scheduled yet)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating actor action: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulations/{simulation_id}/actors/{actor_id}/state")
async def get_actor_state(simulation_id: str, actor_id: str, round_number: int = None):
    """
    Get an actor's state for a specific round.
    
    If round_number is not provided, returns the latest state.
    """
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        # Get current round if not specified
        if round_number is None:
            round_number = simulation.get('current_round', 0)
            if round_number > 0:
                round_number -= 1  # Get last completed round
        
        # Get actor state
        actor_state = storage.get_actor_state(simulation_id, actor_id, round_number)
        
        if not actor_state:
            raise HTTPException(status_code=404, detail=f"No state found for actor {actor_id} in round {round_number}")
        
        return {
            "simulation_id": simulation_id,
            "actor_id": actor_id,
            "round_number": round_number,
            "state": actor_state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting actor state: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulations/{simulation_id}/scheduled-actions/{round_number}")
async def get_scheduled_actions(simulation_id: str, round_number: int):
    """
    Get all actions scheduled for a specific round.
    """
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        scheduled_actions = storage.get_scheduled_actions(simulation_id, round_number)
        
        return {
            "simulation_id": simulation_id,
            "round_number": round_number,
            "actions": scheduled_actions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting scheduled actions: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _process_round_background(simulation_id: str, current_round: int):
    """Background task to process a simulation round."""
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            print(f"❌ Simulation {simulation_id} not found")
            return
        
        print(f"\n{'='*80}")
        print(f"🎮 Processing round {current_round} for simulation: {simulation_id}")
        print(f"   Current round in DB: {current_round}")
        print(f"   Rounds completed: {len(simulation.get('rounds', []))}")
        print(f"{'='*80}\n")
        
        # STEP 1: Generate actions for all active actors
        print(f"🤖 Generating actions for active actors...")
        action_engine = ActorActionEngine()
        
        for actor in simulation.get('actors', []):
            actor_id = actor.get('actor_id')
            if not actor_id:
                continue
                
            try:
                # Get actor state from PREVIOUS round (or create initial state for round 0)
                actor_states = simulation.get('actor_states', {})
                prev_round = current_round - 1
                
                # Build list of other actors for messaging
                other_actors = [
                    {
                        "identifier": a.get('identifier'),
                        "role": a.get('role_in_simulation'),
                        "granularity": a.get('granularity')
                    }
                    for a in simulation.get('actors', [])
                    if a.get('actor_id') != actor_id  # Exclude self
                ]
                
                if prev_round >= 0:
                    # Use previous round's state
                    actor_state = actor_states.get(str(prev_round), {}).get(actor_id, {})
                    if not actor_state:
                        # Fallback if no previous state found
                        actor_state = {
                            "current_time": f"{simulation['time_unit']} {current_round}",
                            "world_state_summary": "Beginning of simulation.",
                            "observations": "No observations yet",
                            "available_actions": ["Investigate", "Plan", "Execute", "Communicate", "Wait"],
                            "my_actions": [],
                            "direct_impacts": "None yet",
                            "indirect_impacts": "None yet",
                            "other_actors": other_actors
                        }
                    else:
                        # Add other_actors to existing state
                        actor_state['other_actors'] = other_actors
                else:
                    # Initial state for round 0
                    actor_state = {
                        "current_time": f"{simulation['time_unit']} {current_round}",
                        "world_state_summary": "Beginning of simulation.",
                        "observations": "No observations yet",
                        "available_actions": ["Investigate", "Plan", "Execute", "Communicate", "Wait"],
                        "my_actions": [],
                        "direct_impacts": "None yet",
                        "indirect_impacts": "None yet",
                        "other_actors": other_actors
                    }
                
                # Generate action(s) and messages for this actor
                action_result = action_engine.generate_action(
                    actor=actor,
                    actor_state=actor_state,
                    question=simulation['question'],
                    time_unit=simulation['time_unit'],
                    current_round=current_round,
                    simulation_duration=simulation['simulation_duration']
                )
                
                # Handle both old format (single action) and new format (actions + messages arrays)
                if 'actions' in action_result:
                    # New format - schedule all actions
                    actions_list = action_result.get('actions', [])
                    messages_list = action_result.get('messages', [])
                    
                    for action_item in actions_list:
                        scheduled_action = {
                            "actor_id": actor_id,
                            "action": action_item['action'],
                            "reasoning": action_item['reasoning'],
                            "scheduled_round": action_item['execute_round'],
                            "duration": action_item['duration'],
                            "random_seed": random.random(),
                            "scheduled_at_round": current_round,
                            "status": "pending"
                        }
                        storage.schedule_action(simulation_id, scheduled_action)
                        print(f"   ✓ {actor.get('identifier')}: {action_item['action'][:50]}...")
                    
                    # Deliver messages to recipients (add to their next round's state)
                    for message in messages_list:
                        to_actor_id = message['to_actor_id']
                        # Find the recipient actor's ID (message uses identifier, we need actor_id)
                        recipient_actor = next((a for a in simulation.get('actors', []) 
                                              if a.get('identifier') == to_actor_id), None)
                        
                        if recipient_actor:
                            # Store message for delivery in next round
                            # We'll add it to a pending_messages collection
                            storage.add_pending_message(simulation_id, {
                                "from_actor_id": actor_id,
                                "from_actor_identifier": actor.get('identifier'),
                                "to_actor_id": recipient_actor['actor_id'],
                                "to_actor_identifier": recipient_actor.get('identifier'),
                                "content": message['content'],
                                "sent_round": current_round,
                                "deliver_round": current_round + 1
                            })
                            print(f"   📨 {actor.get('identifier')} → {to_actor_id}: {message['content'][:40]}...")
                        else:
                            print(f"   ⚠️  Message recipient not found: {to_actor_id}")
                else:
                    # Old format - single action (backwards compatibility)
                    scheduled_action = {
                        "actor_id": actor_id,
                        "action": action_result['action'],
                        "reasoning": action_result['reasoning'],
                        "scheduled_round": action_result['execute_round'],
                        "duration": action_result['duration'],
                        "random_seed": random.random(),
                        "scheduled_at_round": current_round,
                        "status": "pending"
                    }
                    storage.schedule_action(simulation_id, scheduled_action)
                    print(f"   ✓ {actor.get('identifier')}: {action_result['action'][:50]}...")
                
            except Exception as e:
                print(f"   ⚠️  Failed to generate action for {actor.get('identifier')}: {e}")
                traceback.print_exc()
                continue
        
        # STEP 2: Process through world engine
        print(f"\n🌍 Processing round {current_round} through World Engine...")
        world_engine = WorldEngine()
        result = world_engine.process_round(simulation_id, current_round)
        
        # Store round and actor states
        storage.add_round(
            simulation_id=simulation_id,
            round_data=result['round_data'],
            actor_states=result['actor_states']
        )
        
        # Reload to verify increment
        updated_sim = storage.get_simulation(simulation_id)
        new_round = updated_sim.get('current_round', 0)
        print(f"✅ Round {current_round} stored. Next round will be: {new_round}")
        
        # Update status if simulation is complete
        if not result['round_data']['continue_simulation']:
            storage.update_simulation_status(simulation_id, "completed")
            print(f"🏁 Simulation completed!")
        
    except Exception as e:
        print(f"❌ Error processing round: {e}")
        traceback.print_exc()


@app.post("/api/simulations/{simulation_id}/process-round")
async def process_round(simulation_id: str):
    """
    Process the current round of the simulation.
    
    This will:
    1. Get scheduled actions for the current round
    2. Process them through the world engine
    3. Update actor states and store results
    4. Increment the current round
    
    This runs in the background and returns immediately.
    Poll the simulation to check when the round is complete.
    """
    try:
        storage = get_storage()
        simulation = await async_storage_operation(storage.get_simulation, simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        if simulation.get('status') != 'enriched' and simulation.get('status') != 'running':
            raise HTTPException(
                status_code=400, 
                detail=f"Simulation must be enriched before running. Current status: {simulation.get('status')}"
            )
        
        # Update status to running if first round
        if simulation.get('status') == 'enriched':
            await async_storage_operation(storage.update_simulation_status, simulation_id, "running")
        
        current_round = simulation.get('current_round', 0)
        
        # Start round processing in separate thread (don't await, fire and forget)
        loop = asyncio.get_running_loop()
        loop.run_in_executor(executor, _process_round_background, simulation_id, current_round)
        
        # Return immediately
        return {
            "message": "Round processing started",
            "simulation_id": simulation_id,
            "current_round": current_round,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting round processing: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/simulations/{simulation_id}")
async def delete_simulation(simulation_id: str):
    """Delete a simulation."""
    try:
        storage = get_storage()
        deleted = storage.delete_simulation(simulation_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        return {"message": "Simulation deleted", "simulation_id": simulation_id}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
