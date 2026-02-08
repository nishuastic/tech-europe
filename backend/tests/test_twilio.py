"""
Tests for Twilio Service
"""

from app.services.twilio_service import TwilioService, get_hotline_number


def test_get_hotline_number():
    # All targets point to the test number in dev
    assert get_hotline_number("caf") == "+33780827985"
    assert get_hotline_number("prefecture") == "+33780827985"
    assert get_hotline_number("unknown") == "+33780827985"


def test_generate_play_twiml():
    xml = TwilioService.generate_play_twiml(
        audio_url="http://test.com/audio.wav",
        gather_callback="http://test.com/callback",
    )
    assert "<Play>http://test.com/audio.wav</Play>" in xml
    assert "Gather" in xml
    assert 'action="http://test.com/callback"' in xml
    assert 'language="fr-FR"' in xml


def test_generate_stream_twiml():
    xml = TwilioService.generate_stream_twiml("wss://test.com/stream")
    # Attributes can be in any order, so check for key parts
    assert "<Stream" in xml
    assert 'url="wss://test.com/stream"' in xml
