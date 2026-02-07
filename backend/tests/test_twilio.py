"""
Tests for Twilio Service
"""
import pytest
from app.services.twilio_service import TwilioService, get_hotline_number
from unittest.mock import Mock, patch

def test_get_hotline_number():
    assert get_hotline_number("caf") == "+33974394949"
    assert get_hotline_number("prefecture") == "+33821802306"
    assert get_hotline_number("unknown") == "+33974394949"  # Default to CAF

def test_generate_play_twiml():
    xml = TwilioService.generate_play_twiml(
        audio_url="http://test.com/audio.wav",
        gather_callback="http://test.com/callback"
    )
    assert "<Play>http://test.com/audio.wav</Play>" in xml
    assert 'Gather' in xml
    assert 'action="http://test.com/callback"' in xml
    assert 'language="fr-FR"' in xml

def test_generate_stream_twiml():
    xml = TwilioService.generate_stream_twiml("wss://test.com/stream")
    # Attributes can be in any order, so check for key parts
    assert '<Stream' in xml
    assert 'url="wss://test.com/stream"' in xml
    assert 'track="both_tracks"' in xml
