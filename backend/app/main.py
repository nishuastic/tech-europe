from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import agent

app = FastAPI(
    title="Life Admin Copilot API",
    description="Voice-First French Bureaucracy Assistant",
    version="0.1.0",
)

# CORS for Lovable frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For hackathon; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agent.router, prefix="/api/v1/agent", tags=["Agent"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
