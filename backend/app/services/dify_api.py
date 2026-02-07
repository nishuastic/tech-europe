"""
Dify API Service

Handles communication with the Dify API for RAG-powered reasoning.
"""
import httpx
from typing import Optional

from app.config import settings


async def call_dify_chat(
    query: str,
    conversation_id: Optional[str] = None,
    user_id: str = "hackathon-user"
) -> dict:
    """
    Call Dify chat-messages API to get explanation and email draft.
    
    Args:
        query: The transcribed user query
        conversation_id: Optional conversation ID for context continuity
        user_id: User identifier
    
    Returns:
        Dict with Dify response containing explanation and action
    """
    if not settings.dify_api_key:
        raise ValueError("DIFY_API_KEY is not configured")
    
    url = f"{settings.dify_api_url}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {settings.dify_api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",  # Use blocking for simplicity in MVP
        "user": user_id,
    }
    
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def parse_dify_response(dify_response: dict) -> dict:
    """
    Parse the Dify response to extract explanation and email draft.
    
    The Dify workflow should be configured to output structured JSON.
    This function handles both raw text and structured responses.
    
    Args:
        dify_response: Raw response from Dify API
    
    Returns:
        Structured dict with explanation and email_draft
    """
    # Extract the answer from Dify response
    answer = dify_response.get("answer", "")
    conversation_id = dify_response.get("conversation_id", "")
    
    # Try to parse as JSON if Dify returns structured output
    # Otherwise, treat the whole answer as explanation
    try:
        import json
        # Attempt to find JSON in the answer
        if "{" in answer and "}" in answer:
            start = answer.find("{")
            end = answer.rfind("}") + 1
            json_str = answer[start:end]
            parsed = json.loads(json_str)
            return {
                "explanation": parsed.get("explanation", answer),
                "email_draft": parsed.get("email_draft", {}),
                "conversation_id": conversation_id,
                "raw_answer": answer,
            }
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Fallback: return raw answer as explanation
    return {
        "explanation": answer,
        "email_draft": {},
        "conversation_id": conversation_id,
        "raw_answer": answer,
    }
