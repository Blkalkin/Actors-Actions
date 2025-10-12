# Weave Integration for LLM Observability

This project now includes **Weights & Biases Weave** for comprehensive LLM observability and tracing.

## Setup

### 1. Get Your W&B API Key
Visit https://wandb.ai/authorize and copy your API key

### 2. Add to Environment
Add `WANDB_API_KEY` to your `backend/.env`:
```bash
WANDB_API_KEY=xxxxx
```

## What's Been Added

### 1. Dependencies
- Added `weave>=0.51.0` to `backend/requirements.txt`

### 2. Initialization
In `backend/src/api.py`:
```python
import weave
if WANDB_API_KEY:
    os.environ["WANDB_API_KEY"] = WANDB_API_KEY
    weave.init("actors-actions-simulation")
```

### 3. Decorated LLM Functions
All LLM-powered engines now have `@weave.op()` decorators:

- **ActorGenerator** (`actor_generation.py`): `generate()` method
- **ActorEnricher** (`actor_enrichment.py`): `enrich()` method  
- **WorldEngine** (`world_engine.py`): `process_round()` method
- **ActorActionEngine** (`actor_action.py`): `generate_action()` method

## What Weave Tracks

Weave automatically logs:
- ✅ All LLM prompts and responses
- ✅ Token usage and costs
- ✅ Latency and performance metrics
- ✅ Function inputs and outputs
- ✅ Call chains and dependencies
- ✅ Error traces

## Viewing Your Traces

After running your simulation:

1. Visit: https://wandb.ai/
2. Navigate to your Weave dashboard
3. Project name: `actors-actions-simulation`
4. View traces for all LLM calls

## Example Trace Data

When you run a simulation, Weave captures:

```
ActorGenerator.generate()
├─ Input: question = "What happens if the AI bubble pops?"
├─ Model: anthropic/claude-sonnet-4.5
├─ Duration: 2.3s
├─ Tokens: 450 prompt, 1200 completion
└─ Output: {time_unit, simulation_duration, actors[...]}

ActorEnricher.enrich()
├─ Input: actor = {identifier: "YC Startup Founder"}
├─ Model: google/gemini-2.0-flash-exp:free
├─ Duration: 1.8s
└─ Output: {memory, intrinsic_characteristics, predispositions}

WorldEngine.process_round()
├─ Input: simulation_id, round_number
├─ Model: anthropic/claude-sonnet-4.5
├─ Duration: 3.5s
└─ Output: {round_data, actor_states}
```

## Configuration

### Change Project Name
Edit `backend/src/api.py`:
```python
weave.init("your-custom-project-name")
```

### Add Custom Metadata
You can add custom metadata to any traced function:
```python
@weave.op()
def my_function(input_data):
    weave.log({"custom_metric": 123})
    return result
```

## Cost Tracking

Weave automatically tracks OpenRouter API costs. View:
- Cost per simulation
- Cost per actor
- Cost per round
- Cost breakdown by model

## Benefits

1. **Debug Faster**: See exact prompts and responses when things go wrong
2. **Optimize Costs**: Identify expensive operations and optimize
3. **Improve Quality**: Compare outputs across model versions
4. **Monitor Performance**: Track latency and identify bottlenecks
5. **Audit Trail**: Complete history of all LLM interactions

## Local Testing

Run a simulation locally:
```bash
cd backend
python run_server.py
```

Then check your Weave dashboard to see traces appear in real-time!

## Submission Ready

Your project now meets submission requirements:
- ✅ `import weave`
- ✅ `weave.init("actors-actions-simulation")`  
- ✅ `@weave.op()` decorators on all LLM functions

## Questions?

- Weave Docs: https://wandb.ai/site/weave
- Support: support@wandb.com

