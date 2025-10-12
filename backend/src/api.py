"""FastAPI server for the world simulation system."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import traceback

from src.engines.actor_generation import ActorGenerator
from src.engines.actor_enrichment import ActorEnricher
from src.engines.world_engine import WorldEngine
from src.engines.actor_action import ActorActionEngine
from src.storage import get_storage
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
    1. Generates actors based on the question
    2. Stores them in MongoDB
    3. Returns the simulation ID and actors
    """
    try:
        if not request.question or request.question.strip() == "":
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        print(f"\n{'='*80}")
        print(f"📥 Creating simulation: {request.question[:80]}...")
        print(f"{'='*80}\n")
        
        # Generate actors
        generator = ActorGenerator()
        result = generator.generate(request.question)
        
        # Store in MongoDB
        storage = get_storage()
        simulation_id = storage.create_simulation(
            question=request.question,
            time_unit=result['time_unit'],
            simulation_duration=result['simulation_duration'],
            actors=result['actors']
        )
        
        print(f"✅ Created simulation {simulation_id}\n")
        
        return {
            "simulation_id": simulation_id,
            "question": request.question,
            "time_unit": result['time_unit'],
            "simulation_duration": result['simulation_duration'],
            "status": "created",
            "actors": result['actors']
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
        simulation = storage.get_simulation(simulation_id)
        
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
        simulations = storage.list_simulations(limit=limit)
        
        # Add actor count
        for sim in simulations:
            # Get full simulation to count actors
            full_sim = storage.get_simulation(sim['simulation_id'])
            sim['actors_count'] = len(full_sim['actors']) if full_sim else 0
        
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
        rounds = storage.get_rounds(simulation_id)
        
        return {"simulation_id": simulation_id, "rounds": rounds}
        
    except Exception as e:
        print(f"❌ Error retrieving rounds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulations/{simulation_id}/enrich")
async def enrich_simulation(simulation_id: str):
    """
    Enrich all actors in a simulation with detailed profiles.
    
    This calls the enrichment model (Gemini) to research each actor and add:
    - Memory (historical context)
    - Intrinsic characteristics (capabilities, resources, constraints)
    - Predispositions (behavioral patterns, decision-making style)
    
    This can take 2-3 minutes for 7 actors.
    """
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        if simulation.get('status') == 'enriching':
            raise HTTPException(status_code=400, detail="Enrichment already in progress")
        
        if simulation.get('status') == 'enriched':
            return {"message": "Simulation already enriched", "simulation_id": simulation_id}
        
        print(f"\n{'='*80}")
        print(f"🔬 Starting enrichment for simulation: {simulation_id}")
        print(f"   Actors to enrich: {len(simulation['actors'])}")
        print(f"{'='*80}\n")
        
        # Update status to enriching
        storage.update_simulation_status(simulation_id, "enriching")
        
        # Enrich each actor
        enricher = ActorEnricher()
        enriched_count = 0
        
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
                print(f"   Progress: {enriched_count}/{len(simulation['actors'])}")
                
            except Exception as e:
                print(f"⚠️  Failed to enrich {actor['identifier']}: {e}")
                continue
        
        # Update status to enriched
        storage.update_simulation_status(simulation_id, "enriched")
        
        print(f"\n✅ Enrichment complete: {enriched_count}/{len(simulation['actors'])} actors\n")
        
        # Return updated simulation
        updated_simulation = storage.get_simulation(simulation_id)
        return updated_simulation
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error enriching simulation: {e}")
        traceback.print_exc()
        # Update status to failed
        try:
            storage.update_simulation_status(simulation_id, "created")
        except:
            pass
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


@app.post("/api/simulations/{simulation_id}/process-round")
async def process_round(simulation_id: str):
    """
    Process the current round of the simulation.
    
    This will:
    1. Get scheduled actions for the current round
    2. Process them through the world engine
    3. Update actor states and store results
    4. Increment the current round
    """
    try:
        storage = get_storage()
        simulation = storage.get_simulation(simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        if simulation.get('status') != 'enriched' and simulation.get('status') != 'running':
            raise HTTPException(
                status_code=400, 
                detail=f"Simulation must be enriched before running. Current status: {simulation.get('status')}"
            )
        
        current_round = simulation.get('current_round', 0)
        
        print(f"\n{'='*80}")
        print(f"🎮 Processing round {current_round} for simulation: {simulation_id}")
        print(f"{'='*80}\n")
        
        # Update status to running if first round
        if simulation.get('status') == 'enriched':
            storage.update_simulation_status(simulation_id, "running")
        
        # Process through world engine
        world_engine = WorldEngine()
        result = world_engine.process_round(simulation_id, current_round)
        
        # Store round and actor states
        storage.add_round(
            simulation_id=simulation_id,
            round_data=result['round_data'],
            actor_states=result['actor_states']
        )
        
        # Update status if simulation is complete
        if not result['round_data']['continue_simulation']:
            storage.update_simulation_status(simulation_id, "completed")
        
        print(f"✅ Round {current_round} stored\n")
        
        # Return updated simulation
        updated_simulation = storage.get_simulation(simulation_id)
        return updated_simulation
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing round: {e}")
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
