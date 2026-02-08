"""
Audio Bridge

Handles audio format conversion between Twilio and Gradium:
- Twilio Media Streams: mulaw 8kHz
- Gradium STT: PCM 24kHz
- Gradium TTS: ulaw_8000 (native Twilio format!)

Key insight: Gradium TTS supports `ulaw_8000` output,
so TTS→Twilio requires NO conversion.
"""

import audioop
from typing import Tuple


# Twilio Media Streams format
TWILIO_SAMPLE_RATE = 8000
TWILIO_ENCODING = "mulaw"

# Gradium STT format
GRADIUM_STT_SAMPLE_RATE = 24000
GRADIUM_STT_ENCODING = "pcm"

# Gradium TTS format (for Twilio)
GRADIUM_TTS_FORMAT = "ulaw_8000"  # Native Twilio format!


def mulaw_to_pcm(mulaw_data: bytes) -> bytes:
    """
    Convert mu-law encoded audio to PCM 16-bit.

    Args:
        mulaw_data: mu-law encoded audio bytes

    Returns:
        PCM 16-bit audio bytes
    """
    return audioop.ulaw2lin(mulaw_data, 2)  # 2 = 16-bit width


def pcm_to_mulaw(pcm_data: bytes) -> bytes:
    """
    Convert PCM 16-bit audio to mu-law encoding.

    Args:
        pcm_data: PCM 16-bit audio bytes

    Returns:
        mu-law encoded audio bytes
    """
    return audioop.lin2ulaw(pcm_data, 2)


def resample(
    audio_data: bytes, from_rate: int, to_rate: int, state=None
) -> Tuple[bytes, any]:
    """
    Resample audio from one sample rate to another.

    Args:
        audio_data: PCM 16-bit audio bytes
        from_rate: Source sample rate (e.g., 8000)
        to_rate: Target sample rate (e.g., 24000)
        state: Resampling state for continuity across chunks

    Returns:
        Tuple of (resampled audio bytes, new state)
    """
    resampled, new_state = audioop.ratecv(
        audio_data,
        2,  # 16-bit width
        1,  # Mono
        from_rate,
        to_rate,
        state,
    )
    return resampled, new_state


def twilio_to_gradium_stt(mulaw_8k: bytes, resample_state=None) -> Tuple[bytes, any]:
    """
    Convert Twilio audio to Gradium STT format.

    Twilio: mulaw 8kHz → Gradium STT: PCM 24kHz

    Args:
        mulaw_8k: mu-law 8kHz audio from Twilio
        resample_state: State for continuous resampling

    Returns:
        Tuple of (PCM 24kHz audio, new resample state)
    """
    # Step 1: Decode mu-law to PCM 16-bit
    pcm_8k = mulaw_to_pcm(mulaw_8k)

    # Step 2: Resample 8kHz → 24kHz
    pcm_24k, new_state = resample(pcm_8k, 8000, 24000, resample_state)

    return pcm_24k, new_state


def gradium_tts_to_twilio(ulaw_8k: bytes) -> bytes:
    """
    Convert Gradium TTS output to Twilio format.

    When using Gradium TTS with output_format="ulaw_8000",
    the output is already in Twilio's native format!

    This function is a pass-through for clarity.

    Args:
        ulaw_8k: mu-law 8kHz audio from Gradium TTS

    Returns:
        Same audio (no conversion needed)
    """
    return ulaw_8k  # Already in Twilio format!


# Constants for Twilio Media Streams
TWILIO_PAYLOAD_SIZE = 160  # 20ms of audio at 8kHz


def chunk_audio(audio_data: bytes, chunk_size: int = TWILIO_PAYLOAD_SIZE) -> list:
    """
    Split audio into chunks for streaming.

    Args:
        audio_data: Audio bytes
        chunk_size: Size of each chunk

    Returns:
        List of audio chunks
    """
    return [
        audio_data[i : i + chunk_size] for i in range(0, len(audio_data), chunk_size)
    ]


# Gradium STT recommended chunk size
GRADIUM_STT_CHUNK_SIZE = 1920  # 80ms at 24kHz


def chunk_for_gradium_stt(pcm_24k: bytes) -> list:
    """
    Split PCM audio into chunks for Gradium STT.

    Gradium recommends 1920 samples (80ms) per chunk at 24kHz.

    Args:
        pcm_24k: PCM 24kHz audio

    Returns:
        List of audio chunks
    """
    # 1920 samples * 2 bytes/sample = 3840 bytes
    chunk_bytes = GRADIUM_STT_CHUNK_SIZE * 2
    return chunk_audio(pcm_24k, chunk_bytes)
