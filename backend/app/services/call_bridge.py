"""
Call Bridge Manager

Orchestrates the text-to-call flow:
1. User sends text message
2. Translate to French
3. Generate TTS audio
4. Call hotline and play audio
5. Transcribe response
6. Translate back to English
7. Return to user
"""

import asyncio
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
import httpx

from app.services.twilio_service import TwilioService, get_hotline_number
from app.services.gradium_streaming import GradiumSTTStream, VOICE_IDS
from app.services.gradium_tts import text_to_speech
from app.config import settings

logger = logging.getLogger(__name__)


class CallStatus(str, Enum):
    PENDING = "pending"
    TRANSLATING = "translating"
    GENERATING_AUDIO = "generating_audio"
    CALLING = "calling"
    IN_PROGRESS = "in_progress"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CallSession:
    """Represents an active call session."""

    call_id: str
    user_message: str
    target: str
    target_number: str

    # Status tracking
    status: CallStatus = CallStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)

    # Twilio data
    twilio_sid: Optional[str] = None

    # Audio data
    french_message: Optional[str] = None
    audio_url: Optional[str] = None

    # Response data
    french_response: Optional[str] = None
    english_response: Optional[str] = None

    # Error tracking
    error: Optional[str] = None


# In-memory storage (use Redis in production)
_call_sessions: Dict[str, CallSession] = {}


async def translate_to_french(text: str) -> str:
    """Translate English text to French using OpenAI."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate the following English text to formal French suitable for a phone call with a government agency. Only output the translation, nothing else.",
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def translate_to_english(text: str) -> str:
    """Translate French text to English using OpenAI."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate the following French text to English. Only output the translation, nothing else.",
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


class CallBridgeManager:
    """Manages text-to-call bridge operations."""

    def __init__(self):
        self.twilio = TwilioService()

    async def initiate_call(
        self, user_message: str, target: str = "caf"
    ) -> CallSession:
        """
        Start a call to a French hotline.

        Args:
            user_message: The user's message in English
            target: Target hotline (caf, prefecture, impots)

        Returns:
            CallSession with tracking information
        """
        call_id = str(uuid.uuid4())
        target_number = get_hotline_number(target)

        session = CallSession(
            call_id=call_id,
            user_message=user_message,
            target=target,
            target_number=target_number,
        )
        _call_sessions[call_id] = session

        # Run the call flow in background
        asyncio.create_task(self._run_call_flow(session))

        return session

    async def _run_call_flow(self, session: CallSession):
        """Execute the complete call flow."""
        try:
            # Step 1: Translate to French
            session.status = CallStatus.TRANSLATING
            logger.info(f"[{session.call_id}] Translating to French...")
            session.french_message = await translate_to_french(session.user_message)
            logger.info(f"[{session.call_id}] French: {session.french_message}")

            # Step 2: Generate TTS audio
            session.status = CallStatus.GENERATING_AUDIO
            logger.info(f"[{session.call_id}] Generating French TTS...")
            audio_bytes = await text_to_speech(
                session.french_message,
                voice_id=VOICE_IDS["french_female"],
                output_format="wav",
            )

            # Save audio temporarily (in production, upload to S3/GCS)
            audio_filename = f"call_{session.call_id}.wav"
            audio_path = f"/tmp/{audio_filename}"
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            # Use public URL for Twilio to fetch
            session.audio_url = (
                f"{settings.backend_public_url}/api/v1/call/audio/{session.call_id}"
            )

            # Step 3: Initiate Twilio call
            session.status = CallStatus.CALLING
            logger.info(f"[{session.call_id}] Calling {session.target_number}...")
            session.twilio_sid = self.twilio.initiate_call(
                to_number=session.target_number,
                call_id=session.call_id,
            )

            session.status = CallStatus.IN_PROGRESS
            logger.info(f"[{session.call_id}] Call in progress: {session.twilio_sid}")

            # Note: The rest of the flow (transcription) happens via Twilio webhooks

        except Exception as e:
            logger.error(f"[{session.call_id}] Call flow failed: {e}")
            session.status = CallStatus.FAILED
            session.error = str(e)

    async def handle_call_response(self, call_id: str, audio_data: bytes) -> str:
        """
        Handle audio response from the call (CAF's response).

        Args:
            call_id: The call session ID
            audio_data: Audio bytes from Twilio

        Returns:
            English translation of the response
        """
        session = _call_sessions.get(call_id)
        if not session:
            raise ValueError(f"Unknown call: {call_id}")

        session.status = CallStatus.TRANSCRIBING

        try:
            # Transcribe French audio
            stt = GradiumSTTStream(input_format="wav", language="fr")
            await stt.connect()

            # Send audio in chunks
            chunk_size = 1920 * 2  # 80ms at 24kHz, 16-bit
            for i in range(0, len(audio_data), chunk_size):
                await stt.send_audio(audio_data[i : i + chunk_size])

            session.french_response = await stt.receive_transcription()
            await stt.close()

            logger.info(f"[{call_id}] French response: {session.french_response}")

            # Translate to English
            session.english_response = await translate_to_english(
                session.french_response
            )
            session.status = CallStatus.COMPLETED

            logger.info(f"[{call_id}] English response: {session.english_response}")

            return session.english_response

        except Exception as e:
            logger.error(f"[{call_id}] Response handling failed: {e}")
            session.status = CallStatus.FAILED
            session.error = str(e)
            raise

    def get_session(self, call_id: str) -> Optional[CallSession]:
        """Get a call session by ID."""
        return _call_sessions.get(call_id)


# Global instance
call_manager = CallBridgeManager()
