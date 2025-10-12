# Actors-Actions Simulation System

LLM-powered multi-agent simulations where autonomous actors make decisions, send messages, and evolve through discrete time steps.

---

## Quick Start

### 🚀 Deploy to Daytona (Easiest!)

```bash
# Option 1: Using virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-deploy.txt
python deploy_to_daytona.py

# Option 2: Using --user flag
pip install --user -r requirements-deploy.txt
python deploy_to_daytona.py
```

Make sure DAYTONA_API_KEY is in your `backend/.env` file

Get isolated sandbox with preview URLs in 3-5 minutes! Get your Daytona API key from [app.daytona.io/dashboard/keys](https://app.daytona.io/dashboard/keys)

### Local Development

#### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add your API keys
python run_server.py  # → http://localhost:8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev  # → http://localhost:5173
```

---

## Configuration

Create `backend/.env`:

```bash
# Required
DAYTONA_API_KEY=dtn_xxxxx              # Get from https://app.daytona.io/dashboard/keys
OPENROUTER_API_KEY=sk-or-v1-xxxxx      # Get from https://openrouter.ai/keys
MONGODB_URI=mongodb+srv://...          # Get from https://cloud.mongodb.com

# Optional (customize models)
ACTOR_GENERATION_MODEL=anthropic/claude-sonnet-4.5
ENRICHMENT_MODEL=google/gemini-2.0-flash-exp:free
WORLD_ENGINE_MODEL=anthropic/claude-sonnet-4.5
ACTOR_ACTION_MODEL=qwen/qwen-2.5-72b-instruct
```

**MongoDB Setup:** Create free M0 cluster at https://cloud.mongodb.com → Get connection string → Add to `.env`

---

## Usage

1. **Ask a question**: _"What happens if the AI bubble pops?"_
2. **Generate actors**: System creates relevant actors (startups, VCs, etc.)
3. **Enrich** (optional): Add depth to actors via LLM
4. **Simulate**: Actors make decisions, send messages, world evolves
5. **Replay**: Watch completed simulations round-by-round

**API Docs:** http://localhost:8000/docs

---

## Documentation

- **[BACKEND_DESIGN.md](BACKEND_DESIGN.md)** - Complete architecture, data flows, async processing
- **[ACTION_QUEUE_SYSTEM.md](ACTION_QUEUE_SYSTEM.md)** - Action scheduling patterns

---

## Structure

```
backend/src/
├── engines/          # Actor generation, enrichment, actions, world
├── api.py            # FastAPI endpoints + async processing
├── models.py         # Pydantic schemas
├── storage.py        # MongoDB operations
└── prompts.py        # LLM templates

frontend/src/
├── pages/            # Questions list, simulation viewer
├── components/       # Actor visualization, inputs
└── api/              # API client
```

---

## Cost

~$0.29 per simulation (10 actors, 12 rounds) using optimized model routing.

---

## Troubleshooting

**MongoDB SSL Error** → Using certifi fixes this (already in code)  
**401 Unauthorized** → Check `OPENROUTER_API_KEY` in `.env`  
**CORS Errors** → Ensure backend on :8000, frontend on :5173

---

## License

MIT
