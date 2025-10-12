#!/usr/bin/env python3
"""
Deploy Actors-Actions to Daytona using a Dockerfile
This approach is faster for repeated deployments due to caching.

Run: python deploy_dockerfile.py
"""

import os
import ssl
import certifi

# Fix SSL certificate verification issues
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from daytona import Daytona, CreateSnapshotParams, CreateSandboxFromSnapshotParams, Image
from dotenv import load_dotenv

# Load local .env for API keys
load_dotenv("backend/.env")

def main():
    print("🚀 Deploying Actors-Actions with Dockerfile approach...\n")
    
    # Get required environment variables
    daytona_key = os.getenv("DAYTONA_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    mongodb_uri = os.getenv("MONGODB_URI")
    wandb_key = os.getenv("WANDB_API_KEY")
    
    if not daytona_key:
        print("❌ Error: Missing DAYTONA_API_KEY!")
        print("Please add DAYTONA_API_KEY to backend/.env")
        return
    
    if not openrouter_key or not mongodb_uri:
        print("❌ Error: Missing required environment variables!")
        print("Please set OPENROUTER_API_KEY and MONGODB_URI in backend/.env")
        return
    
    if not wandb_key:
        print("⚠️  Warning: WANDB_API_KEY not found - Weave tracing will be disabled")
        print("   Get your key from: https://wandb.ai/authorize")
    
    # Initialize Daytona with API key from .env
    from daytona import DaytonaConfig
    daytona = Daytona(DaytonaConfig(api_key=daytona_key))
    
    snapshot_name = "actors-actions-snapshot"
    
    # Check if snapshot exists
    try:
        existing_snapshots = daytona.snapshot.list()
        snapshot_exists = any(s.name == snapshot_name for s in existing_snapshots.items)
        
        if snapshot_exists:
            print(f"✅ Using existing snapshot: {snapshot_name}\n")
        else:
            print(f"📦 Creating snapshot from Dockerfile...")
            
            # Create snapshot from Dockerfile
            daytona.snapshot.create(
                CreateSnapshotParams(
                    name=snapshot_name,
                    image=Image.from_dockerfile("Dockerfile.daytona"),
                ),
                on_logs=print,
            )
            print(f"✅ Snapshot created: {snapshot_name}\n")
    
    except Exception as e:
        print(f"❌ Error with snapshot: {e}")
        return
    
    # Create sandbox from snapshot
    print("🚀 Creating sandbox from snapshot...")
    
    sandbox = daytona.create(
        CreateSandboxFromSnapshotParams(
            snapshot=snapshot_name,
            env={
                "OPENROUTER_API_KEY": openrouter_key,
                "MONGODB_URI": mongodb_uri,
                "WANDB_API_KEY": wandb_key,
                "ACTOR_GENERATION_MODEL": os.getenv("ACTOR_GENERATION_MODEL", "anthropic/claude-sonnet-4.5"),
                "ENRICHMENT_MODEL": os.getenv("ENRICHMENT_MODEL", "google/gemini-2.0-flash-exp:free"),
                "WORLD_ENGINE_MODEL": os.getenv("WORLD_ENGINE_MODEL", "anthropic/claude-sonnet-4.5"),
                "ACTOR_ACTION_MODEL": os.getenv("ACTOR_ACTION_MODEL", "qwen/qwen-2.5-72b-instruct"),
            },
            auto_stop_interval=0,  # Keep running
        )
    )
    
    print(f"✅ Sandbox created: {sandbox.id}\n")
    
    # Start backend server
    print("🚀 Starting backend server...")
    backend_session = "backend-server"
    sandbox.process.create_session(backend_session)
    sandbox.process.execute_session_command(
        backend_session,
        {
            "command": "cd backend && python run_server.py",
            "var_async": True,
        }
    )
    
    # Start frontend dev server
    print("🚀 Starting frontend server...")
    frontend_session = "frontend-server"
    sandbox.process.create_session(frontend_session)
    sandbox.process.execute_session_command(
        frontend_session,
        {
            "command": "cd frontend && npm run dev -- --host 0.0.0.0 --port 5173",
            "var_async": True,
        }
    )
    
    # Wait for servers to start
    import time
    time.sleep(5)
    
    # Get preview URLs
    backend_preview = sandbox.get_preview_link(8000)
    frontend_preview = sandbox.get_preview_link(5173)
    
    print("\n" + "="*60)
    print("🎉 DEPLOYMENT COMPLETE!")
    print("="*60)
    print(f"\n📍 Backend API:  {backend_preview.url}")
    print(f"   API Docs:     {backend_preview.url}/docs")
    print(f"\n📍 Frontend UI:  {frontend_preview.url}")
    print(f"\n🔑 Sandbox ID:   {sandbox.id}")
    print(f"\n💡 Next time: Use existing snapshot for faster deployment!")
    print(f"💡 To stop: sandbox.stop()")
    print(f"💡 To delete: sandbox.delete()")
    print("\n" + "="*60 + "\n")
    
    return sandbox

if __name__ == "__main__":
    main()

