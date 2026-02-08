
import asyncio
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# Add backend to path
sys.path.append("/Users/nischay/Documents/GitHub/tech-europe/backend")

# Mock dependencies BEFORE importing app modules
sys.modules["app.config"] = MagicMock()
sys.modules["app.services.call_session"] = MagicMock()
sys.modules["app.services.dify_api"] = MagicMock()
sys.modules["app.services.twilio_service"] = MagicMock()
sys.modules["gradium"] = MagicMock()
sys.modules["gradium.client"] = MagicMock()

from app.api.v1.call_media import process_stt

class MockStream:
    def __init__(self, events):
        self._stream = self._generator(events)
    
    async def _generator(self, events):
        for event in events:
            yield event
            await asyncio.sleep(0.1) # Simulate some time passing

class TestThrottling(unittest.IsolatedAsyncioTestCase):
    async def test_throttling_logic(self):
        # Setup mocks
        session = MagicMock()
        session.call_id = "test-call"
        session.transcript = []
        session.add_transcript = MagicMock()
        
        client = MagicMock()
        audio_queue = asyncio.Queue()
        
        # Mock translate function
        translation_counts = 0
        async def mock_translate(text, **kwargs):
            nonlocal translation_counts
            translation_counts += 1
            return f"Translated: {text}"
            
        # Mock notify_frontend
        notify_counts = 0
        async def mock_notify(session, event, data=None):
            nonlocal notify_counts
            pass

        # Prepare a simulation stream
        # 1. "Hello" (text)
        # 2. Wait 1.1s
        # 3. " my name is John Doe" (text, > 20 chars) -> SHOULD TRIGGER (time > 1s and len > 20)
        # 4. Wait 0.5s
        # 5. " and I am calling" (text, < 20 chars) -> NO TRIGGER (len < 20)
        # 6. Wait 0.6s (Total time since last > 1.1s) -> NO TRIGGER (len of NEW text < 20? No, accumulation)
        # 7. " about my application" (text) -> Total new > 20. Time > 1s. -> TRIGGER
        # 8. Hard pause -> FINAL TRIGGER
        
        events = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": " my name is John Doe"}, # Total: "Hello my name is John Doe" (25 chars). 
            # Note: In real app, time passes between events. 
            # We need to simulate time passing in the mock stream or by sleeping in the test?
            # The MockStream generator has a `sleep(0.1)`...
            
            # Let's make the text chunks arrive slowly
        ]
        
        # We need to control time.time() to test throttling deterministically.
        # We can patch time.time
        
        base_time = 1000.0
        
        async def mock_translate(text, **kwargs):
            nonlocal translation_counts
            translation_counts += 1
            return f"Translated: {text}"
            
        with patch("app.api.v1.call_media.translate_to_english", side_effect=mock_translate) as mock_tr, \
             patch("app.api.v1.call_media.notify_frontend", side_effect=mock_notify), \
             patch("app.api.v1.call_media.get_agent_response", new_callable=AsyncMock) as mock_agent, \
             patch("app.api.v1.call_media.time.time") as mock_time:
            
            mock_time.return_value = base_time
            
            # Helper to advance time
            def advance_time(seconds):
                mock_time.return_value += seconds
                
            # Custom stream that advances time
            async def event_generator():
                # T=0: "Hello" (5 chars). New=5. Time=0. -> No trigger (len < 20)
                yield {"type": "text", "text": "Hello"}
                
                advance_time(1.2)
                # T=1.2: " my name is John Doe" (+20 chars). New=25. Time=1.2 (>1.0). -> TRIGGER 1
                yield {"type": "text", "text": " my name is John Doe"}
                
                advance_time(0.5)
                # T=1.7: " short" (+6 chars). New=6. Time=0.5. -> No trigger (len < 20, time < 1.0)
                yield {"type": "text", "text": " short"}
                
                advance_time(0.6) 
                # T=2.3: " phrase" (+7 chars). New=13. Time=1.1. -> No trigger (len < 20)
                yield {"type": "text", "text": " phrase"}
                
                advance_time(0.1)
                 # T=2.4: " completion" (+11 chars). New=24. Time=1.2. -> TRIGGER 2
                yield {"type": "text", "text": " completion"}
                
                advance_time(0.1)
                # Hard pause -> FINAL TRIGGER
                yield {"type": "step", "vad": [{}, {}, {"inactivity_prob": 0.95}]}
                yield {"type": "step", "vad": [{}, {}, {"inactivity_prob": 0.95}]}
                yield {"type": "step", "vad": [{}, {}, {"inactivity_prob": 0.95}]}

            # Make client.stt_stream an AsyncMock so it can be awaited
            async def mock_stt_stream(*args, **kwargs):
                mock_resp = MagicMock()
                mock_resp._stream = event_generator()
                return mock_resp
            
            client.stt_stream = AsyncMock(side_effect=mock_stt_stream)
            
            await process_stt(session, client, audio_queue)
            
            # Expected: 2 intermediate + 1 final = 3 translations
            print(f"Total translations: {translation_counts}")
            self.assertEqual(translation_counts, 3)

if __name__ == "__main__":
    unittest.main()
