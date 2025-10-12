"""Configuration for the world simulation system."""
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "world_simulations")

# Model Configuration
ACTOR_GENERATION_MODEL = os.getenv("ACTOR_GENERATION_MODEL", "anthropic/claude-sonnet-4.5")
ENRICHMENT_MODEL = os.getenv("ENRICHMENT_MODEL", "google/gemini-2.0-flash-exp:free")
WORLD_ENGINE_MODEL = os.getenv("WORLD_ENGINE_MODEL", "anthropic/claude-sonnet-4.5")
ACTOR_ACTION_MODEL = os.getenv("ACTOR_ACTION_MODEL", "qwen/qwen-2.5-72b-instruct")

# Simulation Configuration
MAX_TURNS = 20
ENRICHMENT_MAX_TOKENS = 16000
