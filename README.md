# Actors-Actions World Simulation

A world simulation system that uses LLMs to simulate actors (people, organizations, sectors) responding to social questions over time.

## Project Structure

```
Actors-Actions/
├── backend/           # FastAPI server + simulation engines
│   ├── src/
│   │   ├── engines/   # Actor generation, enrichment, world engine
│   │   ├── api.py     # FastAPI endpoints
│   │   ├── models.py  # Data models
│   │   ├── storage.py # MongoDB interface
│   │   └── prompts.py # All LLM prompts
│   ├── .env           # Your API keys (create from .env.example)
│   └── run_server.py
│
└── frontend/          # React + TypeScript UI
    └── src/
```

## Quick Start

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
python run_server.py
```

Backend runs at `http://localhost:8000`
- API Docs: http://localhost:8000/docs

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`

## Configuration

### Required Environment Variables (backend/.env)

```bash
# OpenRouter API Key (get from https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# MongoDB Atlas (get from https://cloud.mongodb.com)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/...
MONGODB_DATABASE=world_simulations
```

### Optional Model Configuration

```bash
ACTOR_GENERATION_MODEL=anthropic/claude-sonnet-4.5
ENRICHMENT_MODEL=google/gemini-2.0-flash-exp:free
WORLD_ENGINE_MODEL=anthropic/claude-sonnet-4.5
ACTOR_ACTION_MODEL=qwen/qwen-2.5-72b-instruct
```

## MongoDB Setup

1. Go to https://cloud.mongodb.com
2. Create free cluster (M0)
3. Create database user
4. Whitelist IP: 0.0.0.0/0 (for development)
5. Get connection string
6. Add to `backend/.env`

## API Endpoints

### Core Simulation Endpoints
- `POST /api/simulations/create` - Generate actors for a question
- `GET /api/simulations/{id}` - Get simulation details
- `POST /api/simulations/{id}/enrich` - Enrich actors with detailed profiles
- `GET /api/simulations` - List all simulations
- `GET /api/simulations/{id}/rounds` - Get public simulation transcript

### Action Queue Endpoints
- `POST /api/simulations/{id}/schedule-action` - Schedule an action for an actor
- `POST /api/simulations/{id}/actors/{actor_id}/generate-action` - Generate action using AI
- `GET /api/simulations/{id}/actors/{actor_id}/state` - Get actor's current state
- `GET /api/simulations/{id}/scheduled-actions/{round}` - Get actions scheduled for a round
- `POST /api/simulations/{id}/process-round` - Execute current round

## How It Works

### Simulation Flow

1. **Create Simulation**: Generate actors from a question
2. **Enrich Actors**: (Optional) Add detailed profiles
3. **Round Loop**:
   - Actors decide actions (can use AI or manual)
   - Schedule actions in queue (current or future rounds)
   - Process round: World Engine executes scheduled actions
   - World state updates
   - Actors observe outcomes and impacts
   - Repeat until simulation ends

### Actor State

Each actor maintains:
- **Static Profile**: Identity, role, memory, characteristics, predispositions
- **Dynamic State per Round**:
  - Observations and world state
  - Available actions and resources
  - **my_actions**: Full action history with outcomes and private reasoning
  - Direct/indirect impacts from world
  - Messages received

### Data Model

```javascript
simulation: {
  actors: [...],           // Static profiles
  rounds: [...],           // Public transcript
  actor_states: {          // Private states by round
    "0": { actor_id: {...}, ... },
    "1": { actor_id: {...}, ... }
  },
  action_schedule: {       // Queue by round
    "0": [action1, action2],
    "1": [action3]
  },
  active_actions: [...]    // Multi-round actions in progress
}
```

## Architecture

### 1. Actor Generation
- Analyzes question → Determines actors needed
- Uses Claude Sonnet 4.5
- Returns 3-15 actors with roles and interactions
- Each actor gets a unique `actor_id` (UUID)

### 2. Actor Enrichment
- Researches each actor with Gemini 2.0 Flash (free)
- Generates: Memory, Characteristics, Predispositions
- ~10K+ tokens per actor

### 3. Action Queue System
**Actors can:**
- Schedule actions for current or future rounds
- Plan multi-round actions (duration > 1)
- Update their plans each round
- See their full action history with outcomes and reasoning

**Action Flow:**
```
Round 0:
  → Actors decide actions (execute_round, duration)
  → Actions added to action_schedule[execute_round]
  → World Engine processes action_schedule[0]
  → Multi-round actions added to active_actions

Round 1:
  → Actors can update future actions
  → World Engine processes action_schedule[1]
  → Active actions tracked until completion
```

### 4. World Engine
- Processes scheduled actions for each round
- Evaluates success/failure using random seeds
- Updates world state and actor observations
- Manages multi-round action tracking
- Applies stochastic outcomes (random_seed vs threshold)
- Maintains causal consistency

### 5. Actor Action Engine
- AI-powered actor decision making (Qwen 2.5 72B by default)
- Actors receive: world state, observations, full action history, impacts
- Actors can see their own private reasoning from past decisions
- Generates: action, reasoning, execute_round, duration
- Can be used via API or actors can be controlled manually
- Decide actions based on profiles
- Actions processed by world engine

## Data Models

**Actor** - Static profile  
**ActorState** - Dynamic state (changes each turn)  
**ActorAction** - What actor decides to do  
**ActionResult** - Success/failure from world engine  
**WorldUpdate** - World state changes each turn

## Cost Estimates

Per simulation (~7 actors, 10 turns):
- Actor Generation: ~$0.05
- Enrichment: $0 (free Gemini)
- World Engine: ~$0.10
- Actor Actions: ~$0.14
- **Total: ~$0.29**

## Development Status

- [x] Actor Generation ✅
- [x] MongoDB Storage ✅  
- [x] Actor Enrichment ✅
- [x] Data Models ✅
- [x] React Frontend (basic) ✅
- [ ] World Engine
- [ ] Actor Action System
- [ ] Simulation Loop
- [ ] Full UI

## Troubleshooting

**MongoDB SSL Errors**
- Fixed by using certifi certificates in `storage.py`

**OpenRouter Auth Errors**
- Check API key in `backend/.env`
- Verify key is valid at https://openrouter.ai/keys

**CORS Errors**
- Backend has CORS enabled for all origins
- Check backend is running on port 8000

## License

Built for hackathon. Use as you wish.
