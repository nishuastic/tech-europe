"""
Conversation History API

API endpoints for retrieving and managing chat history.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.services.conversation_session import (
    list_conversations,
    get_conversation,
    delete_conversation,
)

router = APIRouter(tags=["conversations"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_conversations():
    """
    Get list of all past conversations.
    Returns summary info for each conversation.
    """
    sessions = list_conversations()
    # Return basic info only
    return [
        {
            "conversation_id": s.conversation_id,
            "title": s.title or "New Conversation",
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "message_count": len(s.messages),
        }
        for s in sessions
    ]


@router.get("/{conversation_id}", response_model=Dict[str, Any])
async def get_single_conversation(conversation_id: str):
    """
    Get full details of a specific conversation, including messages.
    """
    session = get_conversation(conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return session.to_dict()


@router.delete("/{conversation_id}")
async def delete_single_conversation(conversation_id: str):
    """
    Delete a specific conversation.
    """
    session = get_conversation(conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")

    delete_conversation(conversation_id)
    return {"status": "deleted", "conversation_id": conversation_id}
