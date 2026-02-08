from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.services.call_session import list_sessions, get_session, delete_session

router = APIRouter(tags=["history"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_call_history():
    """
    Get list of all past calls.
    Returns summary info for each call.
    """
    sessions = list_sessions()
    return [s.to_dict() for s in sessions]


@router.delete("/{call_id}")
async def delete_call_history(call_id: str):
    """
    Delete a specific call record.
    """
    session = get_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Call not found")

    delete_session(call_id)
    return {"status": "deleted", "call_id": call_id}
