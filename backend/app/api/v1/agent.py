"""
Agent API Router

Handles the core voice-to-insight pipeline.
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.services.gradium_stt import transcribe_audio
from app.services.gradium_tts import (
    text_to_speech,
    text_to_speech_stream,
    text_to_speech_chunked,
    VOICES,
)
from app.services.dify_api import call_dify_chat, parse_dify_response
from app.services.conversation_session import create_conversation, get_conversation


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


class EmailDraft(BaseModel):
    """Email draft structure."""

    subject: str = ""
    body: str = ""
    recipient: str = ""


class CallAction(BaseModel):
    """Call action returned when agent initiates a call."""

    call_id: str
    target: str
    status: str


class ProcessAudioResponse(BaseModel):
    """Response model for audio processing."""

    transcript: str
    explanation: str
    email_draft: EmailDraft
    conversation_id: str
    raw_answer: str
    call_action: Optional[CallAction] = None  # Present when agent triggers call


class ChatRequest(BaseModel):
    """Request model for text chat."""

    message: str
    conversation_id: Optional[str] = None


@router.post("/chat", response_model=ProcessAudioResponse)
async def process_text(request: ChatRequest):
    """
    Process a text message and return an explanation + email draft.

    Same as process-audio but without STT step.
    """
    try:
        logger.info(f"Chat request: {request.message[:50]}...")

        # Look up the Dify conversation ID from our session (if exists)
        dify_conv_id = None
        if request.conversation_id:
            existing_session = get_conversation(request.conversation_id)
            if existing_session and existing_session.dify_conversation_id:
                dify_conv_id = existing_session.dify_conversation_id
                logger.info(f"Found Dify conv_id: {dify_conv_id} for local conv_id: {request.conversation_id}")

        # Call Dify for reasoning
        try:
            dify_response = await call_dify_chat(
                query=request.message,
                conversation_id=dify_conv_id,  # Use Dify's conversation ID, not our local one
            )
            parsed = parse_dify_response(dify_response)
        except Exception as e:
            logger.error(f"Dify API failed: {type(e).__name__}: {e}")
            raise HTTPException(status_code=500, detail=f"Dify API failed: {str(e)}")

        email_draft_data = parsed.get("email_draft") or {}
        call_action_data = parsed.get("call_action")

        # Save to conversation history
        session = None
        if request.conversation_id:
            session = get_conversation(request.conversation_id)

        if not session:
            # Create new session if ID not provided or not found
            # Use metadata conversation_id from Dify if available, else new
            dify_id = parsed.get("conversation_id")
            session = create_conversation(dify_id=dify_id)
        else:
            # Update dify_conversation_id if Dify returned a new one
            new_dify_id = parsed.get("conversation_id")
            if new_dify_id and session.dify_conversation_id != new_dify_id:
                session.dify_conversation_id = new_dify_id
                logger.info(f"Updated session dify_conversation_id to {new_dify_id}")

        # Add user message
        session.add_message("user", request.message)

        # Add agent message
        explanation = parsed.get("explanation", "")
        if explanation:
            session.add_message(
                "assistant",
                explanation,
                metadata={
                    "email_draft": email_draft_data,
                    "call_action": call_action_data,
                },
            )

        # Update conversation_id in response to be OUR internal ID
        # But we also want to keep the dify_id for context?
        # For simplicity, we use our ID as the main one, and store dify_id internally
        response_conv_id = session.conversation_id

        return ProcessAudioResponse(
            transcript=request.message,  # Use the typed message as "transcript"
            explanation=parsed.get("explanation", ""),
            email_draft=EmailDraft(
                subject=email_draft_data.get("subject", "") if email_draft_data else "",
                body=email_draft_data.get("body", "") if email_draft_data else "",
                recipient=email_draft_data.get("recipient", "")
                if email_draft_data
                else "",
            ),
            conversation_id=response_conv_id,
            raw_answer=parsed.get("raw_answer", ""),
            call_action=CallAction(**call_action_data) if call_action_data else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/process-audio", response_model=ProcessAudioResponse)
async def process_audio(
    audio: UploadFile = File(..., description="Audio file to process"),
    conversation_id: Optional[str] = None,
):
    """
    Process an audio file and return an explanation + email draft.

    1. Transcribe audio using Gradium STT
    2. Send transcript to Dify for RAG-powered reasoning
    3. Return structured response with explanation and action
    """
    try:
        # Read audio bytes
        audio_bytes = await audio.read()
        logger.info(
            f"Received audio: {len(audio_bytes)} bytes, filename: {audio.filename}"
        )

        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Step 1: Transcribe audio
        try:
            logger.info("Starting transcription...")
            transcript = await transcribe_audio(
                audio_bytes, audio.filename or "audio.webm"
            )
            logger.info(f"Transcription result: {transcript[:100]}...")
        except Exception as e:
            logger.error(f"Transcription failed: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=500, detail=f"Transcription failed: {str(e)}"
            )

        # Look up the Dify conversation ID from our session (if exists)
        dify_conv_id = None
        if conversation_id:
            existing_session = get_conversation(conversation_id)
            if existing_session and existing_session.dify_conversation_id:
                dify_conv_id = existing_session.dify_conversation_id
                logger.info(f"Found Dify conv_id: {dify_conv_id} for local conv_id: {conversation_id}")

        # Step 2: Call Dify for reasoning
        try:
            logger.info("Calling Dify API...")
            dify_response = await call_dify_chat(
                query=transcript,
                conversation_id=dify_conv_id,  # Use Dify's conversation ID, not our local one
            )
            logger.info("Dify response received")
            parsed = parse_dify_response(dify_response)
        except Exception as e:
            logger.error(f"Dify API failed: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Dify API failed: {str(e)}")

        # Step 3: Structure response
        email_draft_data = parsed.get("email_draft") or {}
        call_action_data = parsed.get("call_action")

        # Save to conversation history
        session = None
        if conversation_id:
            session = get_conversation(conversation_id)

        if not session:
            # Create new session if ID not provided or not found
            dify_id = parsed.get("conversation_id")
            session = create_conversation(dify_id=dify_id)
        else:
            # Update dify_conversation_id if Dify returned a new one
            new_dify_id = parsed.get("conversation_id")
            if new_dify_id and session.dify_conversation_id != new_dify_id:
                session.dify_conversation_id = new_dify_id
                logger.info(f"Updated session dify_conversation_id to {new_dify_id}")

        # Add user message (transcript)
        session.add_message("user", transcript)

        # Add agent message
        explanation = parsed.get("explanation", "")
        if explanation:
            session.add_message(
                "assistant",
                explanation,
                metadata={
                    "email_draft": email_draft_data,
                    "call_action": call_action_data,
                },
            )

        response_conv_id = session.conversation_id

        # Save to conversation history
        session = None
        if conversation_id:
            session = get_conversation(conversation_id)

        if not session:
            # Create new session if ID not provided or not found
            dify_id = parsed.get("conversation_id")
            session = create_conversation(dify_id=dify_id)

        # Add user message (transcript)
        session.add_message("user", transcript)

        # Add agent message
        explanation = parsed.get("explanation", "")
        if explanation:
            session.add_message(
                "assistant",
                explanation,
                metadata={
                    "email_draft": email_draft_data,
                    "call_action": call_action_data,
                },
            )

        response_conv_id = session.conversation_id

        return ProcessAudioResponse(
            transcript=transcript,
            explanation=parsed.get("explanation", ""),
            email_draft=EmailDraft(
                subject=email_draft_data.get("subject", "") if email_draft_data else "",
                body=email_draft_data.get("body", "") if email_draft_data else "",
                recipient=email_draft_data.get("recipient", "")
                if email_draft_data
                else "",
            ),
            conversation_id=response_conv_id,
            raw_answer=parsed.get("raw_answer", ""),
            call_action=CallAction(**call_action_data) if call_action_data else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


class TTSRequest(BaseModel):
    """Request model for TTS."""

    text: str
    voice: str = (
        "english_female"  # english_female, english_male, french_female, french_male
    )


@router.post("/tts")
async def synthesize_speech(request: TTSRequest):
    """
    Convert text to speech using Gradium TTS.

    Returns WAV audio file.
    """
    try:
        # Get voice ID from name
        voice_id = VOICES.get(request.voice, VOICES["english_female"])

        logger.info(f"TTS request: {len(request.text)} chars, voice: {request.voice}")

        audio_bytes = await text_to_speech(
            text=request.text,
            voice_id=voice_id,
            output_format="wav",
        )

        logger.info(f"TTS complete: {len(audio_bytes)} bytes")

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=response.wav"},
        )

    except Exception as e:
        logger.error(f"TTS failed: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")




@router.post("/tts/stream")
async def synthesize_speech_stream(request: TTSRequest):
    """
    Stream text to speech using Gradium TTS.

    Returns streaming PCM audio for low-latency playback.
    """
    try:
        voice_id = VOICES.get(request.voice, VOICES["english_female"])

        logger.info(
            f"TTS stream request: {len(request.text)} chars, voice: {request.voice}"
        )

        async def audio_stream():
            async for chunk in text_to_speech_stream(
                text=request.text,
                voice_id=voice_id,
                output_format="pcm",
            ):
                yield chunk

        return StreamingResponse(
            audio_stream(),
            media_type="audio/pcm",
            headers={
                "Content-Disposition": "inline; filename=response.pcm",
                "X-Sample-Rate": "24000",
                "X-Channels": "1",
            },
        )

    except Exception as e:
        logger.error(f"TTS stream failed: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS stream failed: {str(e)}")


@router.post("/tts/chunked")
async def synthesize_speech_chunked(request: TTSRequest):
    """
    Convert text to speech, streaming audio chunks progressively.

    For long text, this generates each chunk and streams it immediately,
    allowing the frontend to start playback while generating the rest.

    Returns: Multipart stream of WAV audio chunks with JSON metadata.
    """
    try:
        voice_id = VOICES.get(request.voice, VOICES["english_female"])

        logger.info(
            f"TTS chunked request: {len(request.text)} chars, voice: {request.voice}"
        )

        async def generate_chunks():
            import json

            async for chunk_data in text_to_speech_chunked(
                text=request.text,
                voice_id=voice_id,
                output_format="wav",
            ):
                # Send metadata as JSON header
                metadata = {
                    "chunk_index": chunk_data["chunk_index"],
                    "total_chunks": chunk_data["total_chunks"],
                    "is_last": chunk_data["is_last"],
                    "audio_size": len(chunk_data["audio"]),
                }
                # Format: JSON_LENGTH:JSON_DATA:AUDIO_DATA
                meta_json = json.dumps(metadata).encode()
                yield (
                    f"{len(meta_json)}:".encode()
                    + meta_json
                    + b":"
                    + chunk_data["audio"]
                )

                logger.info(
                    f"Sent chunk {chunk_data['chunk_index'] + 1}/{chunk_data['total_chunks']}"
                )

        return StreamingResponse(
            generate_chunks(),
            media_type="application/octet-stream",
            headers={"X-Content-Type": "audio/wav-chunked", "X-Streaming": "true"},
        )

    except Exception as e:
        logger.error(f"TTS chunked failed: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"TTS chunked failed: {str(e)}")
