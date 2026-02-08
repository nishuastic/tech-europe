from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import agent
from app.api.v1 import call_bridge
from app.api.v1 import call_media
from app.api.v1 import call_websocket
from app.api.v1 import history
from app.api.v1 import conversations

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
app.include_router(call_bridge.router, prefix="/api/v1", tags=["Call Bridge"])
app.include_router(call_media.router, tags=["Call Media"])
app.include_router(call_websocket.router, tags=["Call WebSocket"])
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])


app.include_router(
    conversations.router, prefix="/api/v1/conversations", tags=["Conversations"]
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
