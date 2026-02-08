"""
Frontend WebSocket Handler

Handles real-time communication with the React frontend during a call:
- Sends transcription updates from CAF
- Receives user responses to speak to CAF
- Manages call lifecycle events
"""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from app.services.call_session import CallPhase, create_session, get_session
from app.services.twilio_service import TwilioService, get_hotline_number
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/call", tags=["call-websocket"])


class StartCallRequest(BaseModel):
    """Request to start a new interactive call"""

    target: str = "caf"  # caf, prefecture, impots
    user_question: str
    caf_number: Optional[str] = None
    user_name: Optional[str] = None


class StartCallResponse(BaseModel):
    """Response after starting a call"""

    call_id: str
    phase: str
    websocket_url: str


@router.post("/start")
async def start_interactive_call(request: StartCallRequest) -> StartCallResponse:
    """
    Start a new interactive call session.

    Returns a call_id and WebSocket URL for real-time updates.
    """
    # Create session
    session = create_session(target=request.target)
    session.user_question = request.user_question
    session.caf_number = request.caf_number
    session.user_name = request.user_name
    session.phase = CallPhase.READY_TO_CALL

    logger.info(f"[{session.call_id}] Session created for {request.target}")

    # Get WebSocket URL
    ws_url = f"ws://localhost:8000/api/v1/call/ws/{session.call_id}"

    return StartCallResponse(
        call_id=session.call_id,
        phase=session.phase.value,
        websocket_url=ws_url,
    )


@router.post("/dial/{call_id}")
async def dial_call(call_id: str):
    """
    Actually dial the hotline.

    This is separate from start so frontend can connect WebSocket first.
    """
    session = get_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.phase = CallPhase.DIALING

    try:
        twilio = TwilioService()

        # Generate TwiML that uses Media Streams
        media_stream_url = f"wss://{settings.backend_public_url.replace('https://', '')}/api/v1/call/media/{call_id}"

        # Initiate call with Media Streams
        call_sid = twilio.initiate_media_stream_call(
            to_number=get_hotline_number(session.target),
            call_id=call_id,
            media_stream_url=media_stream_url,
        )

        session.twilio_call_sid = call_sid
        logger.info(f"[{call_id}] Call initiated: {call_sid}")

        return {"call_id": call_id, "twilio_sid": call_sid, "status": "dialing"}

    except Exception as e:
        logger.error(f"[{call_id}] Failed to dial: {e}")
        session.phase = CallPhase.FAILED
        session.error = str(e)
        raise HTTPException(status_code=500, detail=str(e))


class InitiateInteractiveCallRequest(BaseModel):
    """Request for Dify tool to initiate an interactive call"""

    target: str = "caf"  # caf, prefecture, impots
    message: str  # User's question/message


class InitiateInteractiveCallResponse(BaseModel):
    """Response for Dify tool - includes call_action for frontend"""

    status: str
    message: str
    call_action: dict  # { call_id, target, status } for frontend


@router.post("/initiate")
async def initiate_interactive_call(
    request: InitiateInteractiveCallRequest,
) -> InitiateInteractiveCallResponse:
    """
    Initiate an interactive call for Dify agent.

    This is the endpoint Dify's call_hotline tool should call.
    It creates a session, dials, and returns a response with call_action
    that the frontend will detect to open the LiveCallUI.

    The response format is designed to be parsed by the frontend when
    included in Dify's response.
    """
    # Create session
    session = create_session(target=request.target)
    session.user_question = request.message
    session.phase = CallPhase.READY_TO_CALL

    logger.info(
        f"[{session.call_id}] Interactive session for {request.target}: {request.message[:50]}..."
    )

    try:
        twilio = TwilioService()

        # Generate Media Streams URL
        backend_host = settings.backend_public_url.replace("https://", "").replace(
            "http://", ""
        )
        media_stream_url = f"wss://{backend_host}/api/v1/call/media/{session.call_id}"

        # Initiate call with Media Streams
        call_sid = twilio.initiate_media_stream_call(
            to_number=get_hotline_number(request.target),
            call_id=session.call_id,
            media_stream_url=media_stream_url,
        )

        session.twilio_call_sid = call_sid
        session.phase = CallPhase.DIALING

        logger.info(f"[{session.call_id}] Call initiated: {call_sid}")

        # Return response with call_action for frontend
        return InitiateInteractiveCallResponse(
            status="calling",
            message=f"I'm now calling {request.target.upper()} for you. The call interface will open automatically.",
            call_action={
                "call_id": session.call_id,
                "target": request.target,
                "status": "dialing",
            },
        )

    except Exception as e:
        logger.error(f"[{session.call_id}] Failed to dial: {e}")
        session.phase = CallPhase.FAILED
        session.error = str(e)

        return InitiateInteractiveCallResponse(
            status="failed",
            message=f"Sorry, I couldn't connect to {request.target.upper()}. Error: {str(e)}",
            call_action={
                "call_id": session.call_id,
                "target": request.target,
                "status": "failed",
            },
        )


@router.websocket("/ws/{call_id}")
async def frontend_websocket(websocket: WebSocket, call_id: str):
    """
    WebSocket connection for frontend real-time updates.

    Events sent to frontend:
    - call_connected: Call connected to CAF
    - caf_speaking_started: CAF started talking
    - caf_said: Transcription of what CAF said (streaming)
    - caf_finished: CAF finished speaking (final transcript)
    - waiting_for_user: Waiting for user response
    - speaking_to_caf: Playing user response to CAF
    - finished_speaking: Finished playing user response
    - call_ended: Call ended
    - error: Error occurred

    Events received from frontend:
    - user_response: User's text response to speak to CAF
    - hangup: End the call
    """
    await websocket.accept()
    logger.info(f"[{call_id}] Frontend WebSocket connected")

    session = get_session(call_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close(code=4004)
        return

    session.frontend_ws = websocket

    # Send current state
    await websocket.send_json(
        {
            "type": "session_state",
            "phase": session.phase.value,
            "target": session.target,
            "question": session.user_question,
        }
    )

    try:
        async for message in websocket.iter_json():
            msg_type = message.get("type")

            if msg_type == "user_response":
                # User typed a response
                english_text = message.get("text", "")
                if not english_text:
                    continue

                logger.info(f"[{call_id}] User response: {english_text[:50]}...")

                # Import here to avoid circular dependency
                from app.api.v1.call_media import speak_to_caf, translate_to_french

                # Translate and speak to CAF
                french_text = await translate_to_french(english_text)
                session.add_transcript("user", french_text, english_text)

                # Speak to CAF (async, will send audio to Twilio)
                await speak_to_caf(session, french_text)

            elif msg_type == "hangup":
                logger.info(f"[{call_id}] User requested hangup")

                # Hangup Twilio call
                if session.twilio_call_sid:
                    try:
                        TwilioService().end_call(session.twilio_call_sid)
                    except Exception as e:
                        logger.error(f"[{call_id}] Failed to hangup Twilio call: {e}")

                session.phase = CallPhase.ENDED
                await websocket.send_json({"type": "call_ended"})
                break

    except WebSocketDisconnect:
        logger.info(f"[{call_id}] Frontend disconnected")
    except Exception as e:
        logger.error(f"[{call_id}] WebSocket error: {e}")
    finally:
        session.frontend_ws = None


@router.get("/session/{call_id}")
async def get_call_session(call_id: str):
    """Get current session state (for polling fallback)"""
    session = get_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.to_dict()


@router.delete("/session/{call_id}")
async def end_call_session(call_id: str):
    """
    End an active call session.
    Doesn't delete the record, just terminates the active call.
    """
    session = get_session(call_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Hangup Twilio call if active
    if session.twilio_call_sid:
        try:
            TwilioService().end_call(session.twilio_call_sid)
        except Exception as e:
            logger.error(f"[{call_id}] Failed to hangup Twilio call: {e}")

    session.phase = CallPhase.ENDED

    # Notify frontend
    if session.frontend_ws:
        try:
            await session.frontend_ws.send_json({"type": "call_ended"})
            await session.frontend_ws.close()
        except Exception:
            pass

    return {"status": "ended", "call_id": call_id}
