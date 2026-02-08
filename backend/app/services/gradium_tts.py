"""
Gradium TTS Service

Handles text-to-speech using the Gradium SDK.
Supports chunking long text and merging audio for responses that exceed API limits.
"""

import gradium
import logging
import io
import wave
from typing import List

from app.config import settings

logger = logging.getLogger(__name__)

# Gradium free tier has a session length limit - chunk to stay safe
MAX_CHUNK_CHARS = 1000  # Safe limit per chunk


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """
    Split text into chunks at sentence boundaries.

    Args:
        text: Full text to split
        max_chars: Maximum characters per chunk

    Returns:
        List of text chunks
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        # Find a good split point (sentence boundary)
        chunk = remaining[:max_chars]
        split_point = -1

        # Try to find sentence endings
        for end in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
            last_end = chunk.rfind(end)
            if last_end > max_chars // 2:
                split_point = last_end + len(end)
                break

        # Fallback to comma or space
        if split_point == -1:
            for sep in [", ", "; ", " "]:
                last_sep = chunk.rfind(sep)
                if last_sep > max_chars // 2:
                    split_point = last_sep + len(sep)
                    break

        # Last resort: hard split
        if split_point == -1:
            split_point = max_chars

        chunks.append(remaining[:split_point].strip())
        remaining = remaining[split_point:].strip()

    logger.info(f"Split {len(text)} chars into {len(chunks)} chunks")
    return chunks


def merge_wav_audio(audio_chunks: List[bytes]) -> bytes:
    """
    Merge multiple WAV audio chunks into a single WAV file.

    Args:
        audio_chunks: List of WAV audio bytes

    Returns:
        Merged WAV audio bytes
    """
    if len(audio_chunks) == 1:
        return audio_chunks[0]

    # Read first chunk to get audio parameters
    first_wav = wave.open(io.BytesIO(audio_chunks[0]), "rb")
    params = first_wav.getparams()

    # Collect all audio frames
    all_frames = []
    for chunk_bytes in audio_chunks:
        wav_file = wave.open(io.BytesIO(chunk_bytes), "rb")
        all_frames.append(wav_file.readframes(wav_file.getnframes()))
        wav_file.close()

    first_wav.close()

    # Write merged audio
    output = io.BytesIO()
    merged_wav = wave.open(output, "wb")
    merged_wav.setparams(params)
    for frames in all_frames:
        merged_wav.writeframes(frames)
    merged_wav.close()

    logger.info(f"Merged {len(audio_chunks)} audio chunks")
    return output.getvalue()


def extract_wav_frames(wav_bytes: bytes) -> tuple:
    """Extract raw PCM frames and params from WAV bytes."""
    wav_file = wave.open(io.BytesIO(wav_bytes), "rb")
    params = wav_file.getparams()
    frames = wav_file.readframes(wav_file.getnframes())
    wav_file.close()
    return params, frames


async def text_to_speech_chunked(
    text: str, voice_id: str = "b35yykvVppLXyw_l", output_format: str = "wav"
):
    """
    Generate TTS for long text, yielding audio chunks progressively.

    This allows the frontend to start playing audio immediately while
    still generating the remaining chunks.

    Yields:
        dict with 'audio' (bytes), 'chunk_index', 'total_chunks', 'is_last'
    """
    if not settings.gradium_api_key:
        raise ValueError("GRADIUM_API_KEY is not configured")

    chunks = chunk_text(text)
    total_chunks = len(chunks)

    logger.info(f"Streaming TTS: {len(text)} chars in {total_chunks} chunks")

    # client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)

    for i, chunk in enumerate(chunks):
        logger.info(f"Generating chunk {i + 1}/{total_chunks} ({len(chunk)} chars)")

        # Instantiate client per chunk to avoid session timeout
        client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)

        result = await client.tts(
            setup={
                "model_name": "default",
                "voice_id": voice_id,
                "output_format": output_format,
            },
            text=chunk,
        )

        yield {
            "audio": result.raw_data,
            "chunk_index": i,
            "total_chunks": total_chunks,
            "is_last": i == total_chunks - 1,
        }


# Voice IDs from Gradium docs
VOICES = {
    "french_female": "b35yykvVppLXyw_l",  # Elise
    "french_male": "axlOaUiFyOZhy4nv",  # Leo
    "english_female": "YTpq7expH9539ERJ",  # Emma
    "english_male": "LFZvm12tW_z0xfGo",  # Kent
}


async def _tts_single_chunk(
    client: gradium.client.GradiumClient, text: str, voice_id: str, output_format: str
) -> bytes:
    """Generate TTS for a single chunk."""
    result = await client.tts(
        setup={
            "model_name": "default",
            "voice_id": voice_id,
            "output_format": output_format,
        },
        text=text,
    )
    return result.raw_data


async def text_to_speech(
    text: str,
    voice_id: str = "b35yykvVppLXyw_l",  # Elise (French)
    output_format: str = "wav",
) -> bytes:
    """
    Convert text to speech using Gradium SDK.

    Automatically chunks long text and merges audio to handle API limits.

    Args:
        text: Text to convert to speech
        voice_id: Gradium voice ID (default: Elise - French)
        output_format: Audio format (wav, pcm, opus)

    Returns:
        Audio bytes
    """
    if not settings.gradium_api_key:
        raise ValueError("GRADIUM_API_KEY is not configured")

    # Split text into chunks
    chunks = chunk_text(text)

    client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)

    if len(chunks) == 1:
        # Single chunk - no merging needed
        return await _tts_single_chunk(client, chunks[0], voice_id, output_format)

    # Multiple chunks - generate in parallel and merge
    logger.info(f"Generating TTS for {len(chunks)} chunks...")

    # Generate audio for each chunk (sequentially to maintain order and avoid rate limits)
    audio_chunks = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)")
        audio = await _tts_single_chunk(client, chunk, voice_id, output_format)
        audio_chunks.append(audio)

    # Merge audio chunks
    if output_format == "wav":
        return merge_wav_audio(audio_chunks)
    else:
        # For PCM/opus, just concatenate raw bytes
        return b"".join(audio_chunks)


async def text_to_speech_stream(
    text: str, voice_id: str = "b35yykvVppLXyw_l", output_format: str = "pcm"
):
    """
    Stream text to speech for low-latency playback.

    Yields:
        Audio chunks as bytes
    """
    if not settings.gradium_api_key:
        raise ValueError("GRADIUM_API_KEY is not configured")

    # For streaming, we process chunks sequentially
    chunks = chunk_text(text)

    client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)

    for chunk in chunks:
        stream = await client.tts_stream(
            setup={
                "model_name": "default",
                "voice_id": voice_id,
                "output_format": output_format,
            },
            text=chunk,
        )

        async for audio_chunk in stream.iter_bytes():
            yield audio_chunk
