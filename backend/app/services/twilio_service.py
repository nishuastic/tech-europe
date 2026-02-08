"""
Twilio Service

Handles outbound phone calls for the text-to-call bridge.
"""

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Connect
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class TwilioService:
    """Service for managing Twilio phone calls."""

    def __init__(self):
        if not all([settings.twilio_account_sid, settings.twilio_auth_token]):
            raise ValueError("Twilio credentials not configured")

        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.phone_number = settings.twilio_phone_number
        self.webhook_base = settings.backend_public_url

    def initiate_call(self, to_number: str, call_id: str) -> str:
        """
        Initiate an outbound call.

        Args:
            to_number: Phone number to call (E.164 format)
            call_id: Internal call ID for tracking

        Returns:
            Twilio Call SID
        """
        call = self.client.calls.create(
            to=to_number,
            from_=self.phone_number,
            url=f"{self.webhook_base}/api/v1/call/twiml/{call_id}",
            status_callback=f"{self.webhook_base}/api/v1/call/status/{call_id}",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            record=True,  # Record for debugging
        )

        logger.info(f"Call initiated: {call.sid} to {to_number}")
        return call.sid

    def end_call(self, call_sid: str) -> bool:
        """
        End an active call.

        Args:
            call_sid: Twilio Call SID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call ended: {call_sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to end call {call_sid}: {e}")
            return False

    @staticmethod
    def generate_play_twiml(audio_url: str, gather_callback: str) -> str:
        """
        Generate TwiML to play audio and gather response.

        Args:
            audio_url: URL of the audio file to play
            gather_callback: URL to call when gathering is complete

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        # Play the French TTS audio
        response.play(audio_url)

        # Gather the response (record what CAF says)
        gather = Gather(
            input="speech",
            action=gather_callback,
            language="fr-FR",
            speech_timeout="auto",
            timeout=30,
        )
        response.append(gather)

        # If no input, hang up
        response.say("Au revoir.", language="fr-FR")

        return str(response)

    @staticmethod
    def generate_stream_twiml(stream_url: str) -> str:
        """
        Generate TwiML to stream audio bidirectionally.

        Uses <Connect><Stream> for bidirectional audio:
        - Send audio TO the call (our TTS)
        - Receive audio FROM the call (CAF's response)

        Args:
            stream_url: WebSocket URL for media streaming

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        # Use Connect with Stream for bidirectional audio
        connect = Connect()
        connect.stream(url=stream_url)
        response.append(connect)

        return str(response)

    def initiate_media_stream_call(
        self, to_number: str, call_id: str, media_stream_url: str
    ) -> str:
        """
        Initiate a call with Media Streams for bidirectional audio.

        Args:
            to_number: Phone number to call (E.164 format)
            call_id: Internal call ID for tracking
            media_stream_url: WebSocket URL for media streaming

        Returns:
            Twilio Call SID
        """
        # Generate TwiML inline
        twiml = self.generate_stream_twiml(media_stream_url)

        call = self.client.calls.create(
            to=to_number,
            from_=self.phone_number,
            twiml=twiml,
            status_callback=f"{self.webhook_base}/api/v1/call/status/{call_id}",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )

        logger.info(f"Media stream call initiated: {call.sid} to {to_number}")
        return call.sid


# French hotline numbers
HOTLINE_NUMBERS = {
    "caf": "+33780827985",  # TEST NUMBER
    "prefecture": "+33780827985",  # TEST NUMBER
    "impots": "+33780827985",  # TEST NUMBER
}


def get_hotline_number(target: str) -> str:
    """Get the phone number for a target hotline."""
    if settings.test_phone_number:
        return settings.test_phone_number
        
    return HOTLINE_NUMBERS.get(target.lower(), HOTLINE_NUMBERS["caf"])
