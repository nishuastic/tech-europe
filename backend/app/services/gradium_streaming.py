"""
Gradium Streaming Service

WebSocket clients for real-time STT and TTS with Gradium.
"""
import asyncio
import base64
import json
import logging
from typing import AsyncGenerator, Callable, Optional
import websockets
from app.config import settings

logger = logging.getLogger(__name__)

# Gradium WebSocket endpoints
GRADIUM_STT_URL = "wss://eu.api.gradium.ai/api/speech/asr"
GRADIUM_TTS_URL = "wss://eu.api.gradium.ai/api/speech/tts"


class GradiumSTTStream:
    """
    Real-time Speech-to-Text using Gradium WebSocket.
    
    Streams audio in, gets text + VAD (voice activity detection) out.
    """
    
    def __init__(self, input_format: str = "pcm", language: str = "fr"):
        self.input_format = input_format
        self.language = language
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.transcript = ""
        self.is_speaking = True
        self._stop_event = asyncio.Event()
    
    async def connect(self):
        """Establish WebSocket connection."""
        headers = {"x-api-key": settings.gradium_api_key}
        self.ws = await websockets.connect(GRADIUM_STT_URL, extra_headers=headers)
        
        # Send setup message
        setup = {
            "type": "setup",
            "model_name": "default",
            "input_format": self.input_format,
        }
        await self.ws.send(json.dumps(setup))
        
        # Wait for ready
        ready = await self.ws.recv()
        ready_data = json.loads(ready)
        if ready_data.get("type") != "ready":
            raise Exception(f"Unexpected response: {ready_data}")
        
        logger.info("Gradium STT connected")
    
    async def send_audio(self, audio_chunk: bytes):
        """Send audio chunk for transcription."""
        if not self.ws:
            raise Exception("Not connected")
        
        msg = {
            "type": "audio",
            "audio": base64.b64encode(audio_chunk).decode()
        }
        await self.ws.send(json.dumps(msg))
    
    async def receive_transcription(self, on_text: Optional[Callable[[str], None]] = None) -> str:
        """
        Receive and process transcription results.
        
        Returns when VAD indicates speaker has finished.
        """
        full_transcript = ""
        
        while not self._stop_event.is_set():
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                data = json.loads(msg)
                
                if data.get("type") == "text":
                    text = data.get("text", "")
                    full_transcript = text  # Gradium sends cumulative
                    if on_text:
                        on_text(text)
                    logger.debug(f"STT: {text}")
                
                elif data.get("type") == "step":
                    # VAD - check if speaker finished
                    vad = data.get("vad", [])
                    if len(vad) >= 3:
                        inactivity_prob = vad[2].get("inactivity_prob", 0)
                        if inactivity_prob > 0.85:
                            logger.info(f"VAD: Speaker finished (prob={inactivity_prob})")
                            self.is_speaking = False
                            break
                
                elif data.get("type") == "end_of_stream":
                    break
                    
            except asyncio.TimeoutError:
                continue
            except websockets.exceptions.ConnectionClosed:
                break
        
        self.transcript = full_transcript
        return full_transcript
    
    async def close(self):
        """Close the WebSocket connection."""
        self._stop_event.set()
        if self.ws:
            # Send end of stream
            await self.ws.send(json.dumps({"type": "end_of_stream"}))
            await self.ws.close()
            self.ws = None


class GradiumTTSStream:
    """
    Real-time Text-to-Speech using Gradium WebSocket.
    
    Sends text, receives audio chunks for streaming playback.
    """
    
    def __init__(self, voice_id: str = "b35yykvVppLXyw_l", output_format: str = "pcm"):
        self.voice_id = voice_id  # Default: Elise (French)
        self.output_format = output_format
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
    
    async def connect(self):
        """Establish WebSocket connection."""
        headers = {"x-api-key": settings.gradium_api_key}
        self.ws = await websockets.connect(GRADIUM_TTS_URL, extra_headers=headers)
        
        # Send setup message
        setup = {
            "type": "setup",
            "model_name": "default",
            "voice_id": self.voice_id,
            "output_format": self.output_format,
        }
        await self.ws.send(json.dumps(setup))
        
        # Wait for ready
        ready = await self.ws.recv()
        ready_data = json.loads(ready)
        if ready_data.get("type") != "ready":
            raise Exception(f"Unexpected response: {ready_data}")
        
        logger.info("Gradium TTS connected")
    
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to audio, yielding chunks.
        
        Args:
            text: Text to synthesize
        
        Yields:
            Audio chunks (PCM bytes)
        """
        if not self.ws:
            raise Exception("Not connected")
        
        # Send text
        await self.ws.send(json.dumps({"type": "text", "text": text}))
        
        # Signal end of text
        await self.ws.send(json.dumps({"type": "end_of_stream"}))
        
        # Receive audio chunks
        while True:
            try:
                msg = await self.ws.recv()
                data = json.loads(msg)
                
                if data.get("type") == "audio":
                    audio_b64 = data.get("audio", "")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                
                elif data.get("type") == "end_of_stream":
                    break
                    
            except websockets.exceptions.ConnectionClosed:
                break
    
    async def synthesize_full(self, text: str) -> bytes:
        """Synthesize text and return complete audio."""
        chunks = []
        async for chunk in self.synthesize(text):
            chunks.append(chunk)
        return b"".join(chunks)
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.ws = None


# Voice IDs for different languages
VOICE_IDS = {
    "french_female": "b35yykvVppLXyw_l",  # Elise
    "french_male": "axlOaUiFyOZhy4nv",    # Leo
    "english_female": "YTpq7expH9539ERJ",  # Emma
    "english_male": "LFZvm12tW_z0xfGo",   # Kent
}
