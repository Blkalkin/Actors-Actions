#!/bin/bash

# 🚀 One-command Daytona deployment for Actors-Actions
# Usage: ./quick-deploy.sh

set -e

echo "🚀 Quick Deploy to Daytona"
echo "=========================="
echo ""

# Check if backend/.env exists
if [ ! -f "backend/.env" ]; then
    echo "❌ Error: backend/.env not found"
    echo ""
    echo "Please create backend/.env with:"
    echo "  DAYTONA_API_KEY=dtn_xxxxx"
    echo "  OPENROUTER_API_KEY=sk-or-v1-xxxxx"
    echo "  MONGODB_URI=mongodb+srv://..."
    echo ""
    exit 1
fi

# Install deployment requirements
echo "📦 Installing deployment dependencies..."
pip install --user -q -r requirements-deploy.txt 2>/dev/null || pip install -q -r requirements-deploy.txt

# Run deployment
echo ""
echo "🚀 Deploying to Daytona..."
echo ""
python deploy_to_daytona.py

echo ""
echo "✅ Done!"

