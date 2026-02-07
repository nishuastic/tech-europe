"""
Twilio Service

Handles outbound phone calls for the text-to-call bridge.
"""
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Play, Gather
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
        
        This allows us to:
        - Send audio TO the call (our TTS)
        - Receive audio FROM the call (CAF's response)
        
        Args:
            stream_url: WebSocket URL for media streaming
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        # Start bidirectional stream
        start = response.start()
        start.stream(url=stream_url, track="both_tracks")
        
        # Keep the call alive
        response.pause(length=300)  # 5 minutes max
        
        return str(response)


# French hotline numbers
HOTLINE_NUMBERS = {
    "caf": "+33780827985",  # TEST NUMBER
    "prefecture": "+33780827985",  # TEST NUMBER
    "impots": "+33780827985",  # TEST NUMBER
}


def get_hotline_number(target: str) -> str:
    """Get the phone number for a target hotline."""
    return HOTLINE_NUMBERS.get(target.lower(), HOTLINE_NUMBERS["caf"])
