"""
Call Bridge API Endpoints

Handles call initiation, status, and Twilio webhooks.
"""
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import logging

from app.services.call_bridge import call_manager, CallStatus
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/call", tags=["Call Bridge"])


class InitiateCallRequest(BaseModel):
    """Request to initiate a call."""
    message: str
    target: str = "caf"  # caf, prefecture, impots


class CallStatusResponse(BaseModel):
    """Response with call status."""
    call_id: str
    status: str
    french_message: Optional[str] = None
    french_response: Optional[str] = None
    english_response: Optional[str] = None
    error: Optional[str] = None


@router.post("/initiate")
async def initiate_call(request: InitiateCallRequest) -> CallStatusResponse:
    """
    Initiate a call to a French hotline.
    
    The call runs asynchronously. Poll /call/status/{call_id} for updates.
    """
    logger.info(f"Initiating call to {request.target}: {request.message[:50]}...")
    
    try:
        session = await call_manager.initiate_call(
            user_message=request.message,
            target=request.target,
        )
        
        return CallStatusResponse(
            call_id=session.call_id,
            status=session.status.value,
            french_message=session.french_message,
        )
    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{call_id}")
async def get_call_status(call_id: str) -> CallStatusResponse:
    """Get the status of a call."""
    session = call_manager.get_session(call_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return CallStatusResponse(
        call_id=session.call_id,
        status=session.status.value,
        french_message=session.french_message,
        french_response=session.french_response,
        english_response=session.english_response,
        error=session.error,
    )


@router.get("/audio/{call_id}")
async def get_call_audio(call_id: str):
    """Serve the TTS audio for Twilio to play."""
    import os
    audio_path = f"/tmp/call_{call_id}.wav"
    
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio not found")
    
    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"call_{call_id}.wav"
    )


@router.post("/twiml/{call_id}")
async def twiml_handler(call_id: str, request: Request):
    """
    Twilio webhook - returns TwiML instructions for the call.
    
    This is called when Twilio connects to the target number.
    """
    session = call_manager.get_session(call_id)
    
    if not session:
        logger.error(f"TwiML requested for unknown call: {call_id}")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>',
            media_type="application/xml"
        )
    
    # Generate TwiML to:
    # 1. Play the French TTS audio
    # 2. Record the response
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{session.audio_url}</Play>
    <Record 
        maxLength="120"
        action="{call_manager.twilio.webhook_base}/api/v1/call/recording/{call_id}"
        transcribe="false"
        playBeep="false"
    />
    <Say language="fr-FR">Au revoir.</Say>
</Response>"""
    
    logger.info(f"[{call_id}] Serving TwiML")
    return Response(content=twiml, media_type="application/xml")


@router.post("/recording/{call_id}")
async def recording_handler(call_id: str, request: Request):
    """
    Twilio webhook - handles the recorded response.
    
    Downloads the recording and processes it.
    """
    form_data = await request.form()
    recording_url = form_data.get("RecordingUrl")
    recording_sid = form_data.get("RecordingSid")
    
    logger.info(f"[{call_id}] Recording received: {recording_sid}")
    
    if recording_url:
        # Download recording from Twilio
        import httpx
        from app.config import settings
        
        async with httpx.AsyncClient() as client:
            # Add .wav extension for format
            audio_response = await client.get(
                f"{recording_url}.wav",
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            audio_data = audio_response.content
        
        # Process the recording
        try:
            english_response = await call_manager.handle_call_response(call_id, audio_data)
            logger.info(f"[{call_id}] Response processed: {english_response[:100]}...")
        except Exception as e:
            logger.error(f"[{call_id}] Failed to process recording: {e}")
    
    # Return TwiML to end the call
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>',
        media_type="application/xml"
    )


@router.post("/status/{call_id}")
async def status_callback(call_id: str, request: Request):
    """
    Twilio status callback webhook.
    
    Receives updates about call status (ringing, answered, completed, etc.)
    """
    form_data = await request.form()
    call_status = form_data.get("CallStatus")
    
    logger.info(f"[{call_id}] Twilio status: {call_status}")
    
    session = call_manager.get_session(call_id)
    if session:
        if call_status == "completed":
            if session.status == CallStatus.IN_PROGRESS:
                session.status = CallStatus.COMPLETED
        elif call_status in ["busy", "no-answer", "canceled", "failed"]:
            session.status = CallStatus.FAILED
            session.error = f"Call {call_status}"
    
    return {"status": "ok"}
