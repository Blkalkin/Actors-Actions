#!/usr/bin/env python3
"""
Deploy Actors-Actions project to Daytona
Run: python deploy_to_daytona.py
"""

import os
import ssl
import certifi

# Fix SSL certificate verification issues
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from daytona import Daytona, CreateSandboxFromImageParams, Image
from dotenv import load_dotenv

# Load local .env for API keys
load_dotenv("backend/.env")

def main():
    print("🚀 Deploying Actors-Actions to Daytona...\n")
    
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
    
    # Create a snapshot with Python and Node.js
    print("📦 Creating sandbox with Python + Node.js environment...")
    
    image = (
        Image.debian_slim("3.12")
        .run_commands(
            # Update and install system dependencies first
            "apt-get update && apt-get install -y curl git ca-certificates",
            # Install Node.js 20
            "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
            "apt-get install -y nodejs",
            # Verify installations
            "node --version && npm --version"
        )
        .pip_install([
            "openai>=1.54.0",
            "python-dotenv>=1.0.0",
            "fastapi>=0.115.0",
            "uvicorn>=0.32.0",
            "pymongo>=4.10.0",
            "weave>=0.51.0",
        ])
        .workdir("/home/daytona/actors-actions")
    )
    
    # Create sandbox
    sandbox = daytona.create(
        CreateSandboxFromImageParams(
            image=image,
            env={
                "OPENROUTER_API_KEY": openrouter_key,
                "MONGODB_URI": mongodb_uri,
                "WANDB_API_KEY": wandb_key,
            },
            auto_stop_interval=0,  # Keep running indefinitely
        ),
        timeout=0,  # Wait for image build
        on_snapshot_create_logs=print,
    )
    
    print(f"\n✅ Sandbox created: {sandbox.id}\n")
    
    # Upload project files
    print("📤 Uploading project files...")
    import tarfile
    import io
    
    # Create tar of project (excluding node_modules, .git, etc.)
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
        tar.add('backend', arcname='backend', filter=lambda t: t if 'node_modules' not in t.name and '.git' not in t.name and '__pycache__' not in t.name else None)
        tar.add('frontend', arcname='frontend', filter=lambda t: t if 'node_modules' not in t.name and '.git' not in t.name and 'dist' not in t.name else None)
    
    tar_buffer.seek(0)
    sandbox.fs.upload_file(tar_buffer.read(), "project.tar.gz")
    sandbox.process.exec("tar -xzf project.tar.gz && rm project.tar.gz")
    
    print("✅ Files uploaded\n")
    
    # Install frontend dependencies
    print("📦 Installing frontend dependencies...")
    result = sandbox.process.exec("npm install", cwd="frontend")
    if result.exit_code != 0:
        print(f"❌ Frontend install failed: {result.result}")
        return
    
    print("✅ Frontend dependencies installed\n")
    
    # Build frontend
    print("🏗️ Building frontend...")
    result = sandbox.process.exec("npm run build", cwd="frontend")
    if result.exit_code != 0:
        print(f"❌ Frontend build failed: {result.result}")
        return
    
    print("✅ Frontend built\n")
    
    # Start backend server in a session
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
    
    # Start frontend dev server in a session
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
    
    # Wait a moment for servers to start
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
    print(f"\n💡 To stop: sandbox.stop()")
    print(f"💡 To delete: sandbox.delete()")
    print("\n" + "="*60 + "\n")
    
    return sandbox

if __name__ == "__main__":
    main()

