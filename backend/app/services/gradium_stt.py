"""
Gradium STT Service

Handles speech-to-text transcription using the Gradium SDK.
"""

import asyncio
import tempfile
from pathlib import Path

import gradium

from app.config import settings


async def convert_to_wav(input_path: str, output_path: str) -> bool:
    """Convert audio file to WAV format using ffmpeg."""
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-ar",
            "24000",  # Gradium expects 24kHz for STT
            "-ac",
            "1",  # Mono
            "-f",
            "wav",
            output_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.wait()
        return process.returncode == 0
    except Exception:
        return False


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio bytes to text using Gradium SDK.

    Args:
        audio_bytes: Raw audio data
        filename: Original filename (for format detection)

    Returns:
        Transcribed text string
    """
    if not settings.gradium_api_key:
        raise ValueError("GRADIUM_API_KEY is not configured")

    client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)

    # Save audio to temp file
    suffix = Path(filename).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    wav_path = None

    try:
        # Convert to WAV if not already wav format
        if suffix.lower() != ".wav":
            wav_path = tmp_path.replace(suffix, ".wav")
            converted = await convert_to_wav(tmp_path, wav_path)
            if converted and Path(wav_path).exists():
                audio_path = wav_path
                input_format = "wav"
            else:
                # Fallback: try original format
                audio_path = tmp_path
                input_format = "opus" if suffix in [".opus", ".ogg", ".webm"] else "wav"
        else:
            audio_path = tmp_path
            input_format = "wav"

        # Use SDK streaming STT
        async def audio_generator(data, chunk_size=1920):
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

        # Read file as bytes for streaming
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        stream = await client.stt_stream(
            {"model_name": "default", "input_format": input_format},
            audio_generator(audio_data),
        )

        transcribed_text = ""
        async for message in stream.iter_text():
            # message is TextWithTimestamps object with .text attribute
            if hasattr(message, "text"):
                transcribed_text += message.text + " "
            else:
                transcribed_text += str(message) + " "

        return transcribed_text.strip()

    finally:
        Path(tmp_path).unlink(missing_ok=True)
        if wav_path:
            Path(wav_path).unlink(missing_ok=True)
