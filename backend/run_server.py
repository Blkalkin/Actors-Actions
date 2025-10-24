"""Run the FastAPI server."""
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Actors-Actions API Server...")
    print("📝 API Documentation: http://localhost:8000/docs")
    print("💚 Health check: http://localhost:8000/health")
    print("\n" + "="*80 + "\n")
    
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )

