"""
Gradium TTS Service

Handles text-to-speech using the Gradium SDK.
"""
import gradium

from app.config import settings

# Voice IDs from Gradium docs
VOICES = {
    "french_female": "b35yykvVppLXyw_l",  # Elise
    "french_male": "axlOaUiFyOZhy4nv",    # Leo
    "english_female": "YTpq7expH9539ERJ", # Emma
    "english_male": "LFZvm12tW_z0xfGo",   # Kent
}


async def text_to_speech(
    text: str,
    voice_id: str = "b35yykvVppLXyw_l",  # Elise (French)
    output_format: str = "wav"
) -> bytes:
    """
    Convert text to speech using Gradium SDK.
    
    Args:
        text: Text to convert to speech
        voice_id: Gradium voice ID (default: Elise - French)
        output_format: Audio format (wav, pcm, opus)
    
    Returns:
        Audio bytes
    """
    if not settings.gradium_api_key:
        raise ValueError("GRADIUM_API_KEY is not configured")
    
    client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)
    
    result = await client.tts(
        setup={
            "model_name": "default",
            "voice_id": voice_id,
            "output_format": output_format,
        },
        text=text,
    )
    
    return result.raw_data


async def text_to_speech_stream(
    text: str,
    voice_id: str = "b35yykvVppLXyw_l",
    output_format: str = "pcm"
):
    """
    Stream text to speech for low-latency playback.
    
    Yields:
        Audio chunks as bytes
    """
    if not settings.gradium_api_key:
        raise ValueError("GRADIUM_API_KEY is not configured")
    
    client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)
    
    stream = await client.tts_stream(
        setup={
            "model_name": "default",
            "voice_id": voice_id,
            "output_format": output_format,
        },
        text=text,
    )
    
    async for audio_chunk in stream.iter_bytes():
        yield audio_chunk
