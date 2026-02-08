"""
Twilio Media Streams WebSocket Handler

Handles bidirectional audio streaming between Twilio and Gradium:
1. Receives audio from CAF (via Twilio) → STT → Translate → Frontend
2. Receives text from user (via Frontend) → Translate → TTS → Twilio → CAF
"""

import asyncio
import base64
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import gradium

from app.config import settings
from app.services.call_session import CallSession, CallPhase, get_session
from app.services.audio_bridge import (
    twilio_to_gradium_stt,
    GRADIUM_TTS_FORMAT,
)
from app.services.dify_api import translate_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/call", tags=["call-media"])

# French voice ID for TTS (from Gradium) - Elise
FRENCH_VOICE_ID = "b35yykvVppLXyw_l"


async def translate_to_english(french_text: str) -> str:
    """Translate French to English using Dify/OpenAI"""
    try:
        result = await translate_text(french_text, source_lang="fr", target_lang="en")
        return result
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return french_text  # Fallback to original


async def translate_to_french(english_text: str) -> str:
    """Translate English to French using Dify/OpenAI"""
    try:
        result = await translate_text(english_text, source_lang="en", target_lang="fr")
        return result
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return english_text


async def notify_frontend(session: CallSession, event_type: str, data: dict = None):
    """Send event to connected frontend WebSocket"""
    if session.frontend_ws:
        try:
            message = {"type": event_type, **(data or {})}
            await session.frontend_ws.send_json(message)
            logger.debug(f"[{session.call_id}] → Frontend: {event_type}")
        except Exception as e:
            logger.error(f"Failed to notify frontend: {e}")


async def get_agent_response(
    session: CallSession, caf_said: str, user_question: str
) -> dict:
    """
    Ask Dify agent for a response to what CAF said.
    Returns: Dict with keys 'message' (str) and optional 'action' (dict).
    """
    from app.services.dify_api import call_dify_chat, parse_dify_response

    # Construct transcript from session history
    conversation_context = []
    for entry in session.transcript:
        speaker_name = "CAF" if entry.speaker == "caf" else "User"
        conversation_context.append(f"{speaker_name}: {entry.english_text}")

    # We provide structured inputs to Dify so the System Prompt can handle the logic.
    # The 'query' trigger is the immediate event (CAF spoke).
    dify_inputs = {
        "user_question": user_question,
        "transcript": chr(10).join(conversation_context),
        "caf_last_message": caf_said,
    }

    trigger_query = f"CAF just said: '{caf_said}'. Generate the next response. IMPORTANT: Keep your response very short and concise (max 2 sentences) unless asked for details."

    try:
        logger.info(f"[{session.call_id}] Asking agent for response...")

        dify_response = await call_dify_chat(
            query=trigger_query,
            inputs=dify_inputs,
            conversation_id=session.dify_conversation_id,
        )

        parsed = parse_dify_response(dify_response)

        # Save conversation ID for context
        if parsed.get("conversation_id"):
            session.dify_conversation_id = parsed["conversation_id"]

        response_text = parsed.get("explanation", "").strip()
        action = parsed.get("action")

        logger.info(
            f"[{session.call_id}] Agent suggests: {response_text[:50]}... (Action: {action})"
        )

        return {"message": response_text, "action": action}

    except Exception as e:
        logger.error(f"[{session.call_id}] Agent response error: {e}")
        return {"message": None, "action": None}


def is_repetition_loop(session: CallSession, new_response: str) -> bool:
    """
    Check if the agent is stuck in a loop repeating the same thing.

    Returns True if:
    1. The new response is very similar to the last thing the agent said.
    2. The last thing CAF said was a short acknowledgement (indicating they are waiting).
    """
    # 1. Get last agent message
    last_agent_msg = None
    for entry in reversed(session.transcript):
        if entry.speaker == "user":
            last_agent_msg = entry.english_text
            break

    if not last_agent_msg:
        return False

    # 2. Check similarity (simple exact match or contains for now)
    # Normalize to avoid minor diffs
    msg1 = last_agent_msg.lower().strip()
    msg2 = new_response.lower().strip()

    if msg1 not in msg2 and msg2 not in msg1:
        return False

    # 3. Check if CAF's last message was just an acknowledgement
    last_caf_msg = None
    for entry in reversed(session.transcript):
        if entry.speaker == "caf":
            last_caf_msg = entry.english_text
            break

    if not last_caf_msg:
        return False

    # List of short acknowledgements
    acks = [
        "sure",
        "okay",
        "ok",
        "d'accord",
        "bien sûr",
        "yes",
        "oui",
        "understood",
        "good",
    ]

    # If CAF said something short (< 20 chars) or contained an ack
    caf_said_ack = len(last_caf_msg) < 20 or any(
        ack in last_caf_msg.lower() for ack in acks
    )

    if caf_said_ack:
        logger.warning(
            f"[{session.call_id}] Loop detected! Agent wants to repeat '{new_response}' after ack."
        )
        return True

    return False


@router.websocket("/media/{call_id}")
async def twilio_media_stream(websocket: WebSocket, call_id: str):
    """
    Handle Twilio Media Streams WebSocket connection.

    This endpoint receives real-time audio from Twilio (CAF side)
    and can send audio back to Twilio (user responses).

    Twilio Media Stream Events:
    - connected: Stream connected
    - start: Stream started with metadata
    - media: Audio payload (base64 encoded mulaw)
    - stop: Stream stopped
    """
    await websocket.accept()
    logger.info(f"[{call_id}] Twilio Media Stream connected")

    session = get_session(call_id)
    if not session:
        logger.error(f"[{call_id}] Session not found")
        await websocket.close(code=4004)
        return

    session.twilio_ws = websocket
    session.phase = CallPhase.CONNECTED
    await notify_frontend(session, "call_connected")

    # State for audio processing
    resample_state = None
    gradium_client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)

    # Audio buffer for STT
    audio_buffer = asyncio.Queue()

    # Start STT processing task
    stt_task = asyncio.create_task(process_stt(session, gradium_client, audio_buffer))

    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                logger.info(f"[{call_id}] Media stream connected")

            elif event == "start":
                session.twilio_stream_sid = data.get("streamSid")
                logger.info(f"[{call_id}] Stream started: {session.twilio_stream_sid}")

                # Speak the initial greeting (just "Bonjour" or similar)
                session.phase = CallPhase.WAITING_GREETING_RESPONSE
                await notify_frontend(session, "speaking_initial_greeting")

                # Simple greeting
                french_greeting = "Bonjour, allô?"

                logger.info(f"[{call_id}] Speaking greeting: {french_greeting}")
                await speak_to_caf(session, french_greeting)

                # Now listen for CAF's response - do NOT speak user question yet
                session.phase = CallPhase.WAITING_GREETING_RESPONSE
                await notify_frontend(
                    session,
                    "caf_speaking_started",
                    {"status": "listening_for_greeting"},
                )

            elif event == "media":
                # Receive audio from CAF
                payload = data.get("media", {}).get("payload", "")
                if payload:
                    mulaw_audio = base64.b64decode(payload)

                    # Convert to Gradium STT format
                    pcm_audio, resample_state = twilio_to_gradium_stt(
                        mulaw_audio, resample_state
                    )

                    # Queue for STT processing
                    await audio_buffer.put(pcm_audio)

            elif event == "stop":
                logger.info(f"[{call_id}] Media stream stopped")
                session.phase = CallPhase.ENDED
                await notify_frontend(session, "call_ended")
                break

    except WebSocketDisconnect:
        logger.info(f"[{call_id}] Twilio disconnected")
    except Exception as e:
        logger.error(f"[{call_id}] Media stream error: {e}")
        session.error = str(e)
        session.phase = CallPhase.FAILED
    finally:
        stt_task.cancel()
        session.twilio_ws = None


async def process_stt(
    session: CallSession,
    client: gradium.client.GradiumClient,
    audio_queue: asyncio.Queue,
):
    """
    Process incoming audio through Gradium STT.
    """
    # logger.info(f"[{session.call_id}] Starting STT processing") # Reduced log

    async def audio_generator():
        """Yield audio chunks from queue"""
        while True:
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                yield chunk
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    try:
        stt_stream = await client.stt_stream(
            {
                "model_name": "default",
                "input_format": "pcm",
                "json_config": {"language": "fr"},
            },
            audio_generator(),
        )

        current_text = ""
        last_translated_text = ""
        last_translation = ""
        last_translation_time = 0

        # New: Track consecutive silence for VAD
        vad_silence_counter = 0
        SILENCE_THRESHOLD = 3  # frames

        # New: Track if this is the first turn
        # is_first_turn = True

        async for msg in stt_stream._stream:
            msg_type = msg.get("type")

            if msg_type == "text":
                # CAF said something
                french_chunk = msg.get("text", "")

                # Filter out empty or very short inputs (likely noise)
                if not french_chunk or len(french_chunk.strip()) < 1:
                    continue

                # Gradium sends chunks (deltas), so we accumulate
                if current_text:
                    current_text += " " + french_chunk
                else:
                    current_text = french_chunk

                # --- INTERMEDIATE TRANSLATION STRATEGY ---
                # User request: "Every 1 second then and 20 chars"
                
                new_content_len = len(current_text) - len(last_translated_text)
                now = time.time()
                time_since_last = now - last_translation_time
                
                # Check soft pause (VAD > 0.6)
                # We can't easily check VAD here because we are in the "text" message block, not "step" (VAD) block.
                # However, we can use the time-based trigger as the primary driver for intermediate results.
                
                # Trigger if:
                # 1. We have enough new content (> 20 chars)
                # 2. AND enough time has passed (> 1.0s)
                if new_content_len > 20 and time_since_last > 1.0:
                    english_text = await translate_to_english(current_text)
                    last_translation = english_text
                    last_translated_text = current_text
                    last_translation_time = now

                    # Send accumulated French + latest English to frontend
                    await notify_frontend(
                        session,
                        "caf_said",
                        {
                            "french": current_text,
                            "english": english_text,
                            "is_final": False,
                        },
                    )

            elif msg_type == "step":
                # VAD: Check if CAF paused or stopped talking
                vad = msg.get("vad", [])
                if len(vad) >= 3:
                    inactivity_prob = vad[2].get("inactivity_prob", 0)

                    # --- HARD PAUSE (Finalize) ---
                    # Stricter VAD: Require consecutive silent frames
                    if inactivity_prob > 0.90:
                        vad_silence_counter += 1
                    else:
                        vad_silence_counter = 0

                    if vad_silence_counter >= SILENCE_THRESHOLD and current_text:
                        # CAF finished speaking (Hard Pause)
                        english_final = await translate_to_english(current_text)

                        # Add to transcript
                        session.add_transcript("caf", current_text, english_final)

                        # Notify frontend of what CAF said (with final English translation)
                        await notify_frontend(
                            session,
                            "caf_finished",
                            {"french": current_text, "english": english_final},
                        )

                        # === AUTO-HANGUP CHECK ===
                        termination_phrases = [
                            "au revoir",
                            "goodbye",
                            "bonne journée",
                            "bon journée",
                            "bye",
                            "a bientôt",
                        ]
                        if any(
                            phrase in english_final.lower()
                            for phrase in termination_phrases
                        ) or any(
                            phrase in current_text.lower()
                            for phrase in termination_phrases
                        ):
                            logger.info(
                                f"[{session.call_id}] Termination phrase detected. Hanging up."
                            )
                            from app.services.twilio_service import TwilioService

                            TwilioService().end_call(session.twilio_call_sid)
                            session.phase = CallPhase.ENDED
                            await notify_frontend(session, "call_ended")
                            break

                        # === INITIAL GREETING FLOW ===
                        if session.phase == CallPhase.WAITING_GREETING_RESPONSE:
                            logger.info(
                                f"[{session.call_id}] CAF responded to greeting. Sending user request."
                            )

                            # Now send the actual user question
                            user_msg = session.user_question

                            # Conciseness prompt is handled in get_agent_response, but here we just translate/speak
                            french_req = await translate_to_french(user_msg)
                            session.add_transcript("user", french_req, user_msg)
                            await speak_to_caf(session, french_req)

                            session.phase = CallPhase.CAF_SPEAKING
                            current_text = ""
                            vad_silence_counter = 0
                            continue

                        # === AGENT-MEDIATED FLOW ===
                        # Ask Dify for suggested response
                        session.phase = CallPhase.WAITING_USER
                        await notify_frontend(
                            session,
                            "agent_thinking",
                            {"message": "Crafting response..."},
                        )

                        # Get agent's suggested response
                        agent_result = await get_agent_response(
                            session,
                            caf_said=english_final,
                            user_question=session.user_question,
                        )

                        agent_message = agent_result.get("message")
                        agent_action = agent_result.get("action")

                        # Handle specific actions
                        if agent_action and agent_action.get("type") == "ask_user":
                            # 1. Speak the filler message to CAF (if valid)
                            if agent_message:
                                french_filler = await translate_to_french(agent_message)
                                await speak_to_caf(session, french_filler)

                            # 2. Ask user for input
                            question = agent_action.get(
                                "question", "Agent needs your help."
                            )
                            logger.info(
                                f"[{session.call_id}] Action ASK_USER: {question}"
                            )

                            await notify_frontend(
                                session, "waiting_for_user", {"prompt": question}
                            )
                            current_text = ""
                            vad_silence_counter = 0
                            continue  # Stop here, wait for user input

                        # Check termination in agent response
                        if agent_message:
                            if any(
                                phrase in agent_message.lower()
                                for phrase in termination_phrases
                            ):
                                logger.info(
                                    f"[{session.call_id}] Agent said goodbye. Hanging up soon."
                                )
                                # We'll hang up AFTER speaking

                        # Normal flow
                        if agent_message:
                            # Check for repetition loop
                            if is_repetition_loop(session, agent_message):
                                logger.warning(
                                    f"[{session.call_id}] Loop detected, stopping auto-response"
                                )
                                await notify_frontend(
                                    session,
                                    "waiting_for_user",
                                    {
                                        "prompt": f"I'm stuck in a loop. Last thing CAF said was '{english_final}'. What should I say?"
                                    },
                                )
                                current_text = ""
                                vad_silence_counter = 0
                                continue

                            # Send agent's suggestion to frontend
                            await notify_frontend(
                                session,
                                "agent_suggests",
                                {
                                    "english": agent_message,
                                    "auto_send": True,  # Auto-send after delay
                                    "auto_send_delay": 3000,  # 3 seconds
                                },
                            )

                            # Auto-speak to CAF (agent-mediated mode)
                            french_response = await translate_to_french(agent_message)
                            session.add_transcript(
                                "user", french_response, agent_message
                            )
                            await speak_to_caf(session, french_response)
                        else:
                            # Fallback to waiting for user
                            await notify_frontend(
                                session,
                                "waiting_for_user",
                                {"prompt": "CAF is waiting for your response"},
                            )

                        # Reset accumulator for next turn
                        current_text = ""
                        vad_silence_counter = 0

            elif msg_type == "end_of_stream":
                # logger.info(f"[{session.call_id}] STT stream ended") # Reduced log
                break

    except asyncio.CancelledError:
        pass  # Expected on disconnect
    except Exception as e:
        logger.error(f"[{session.call_id}] STT error: {e}")


async def speak_to_caf(session: CallSession, french_text: str):
    """
    Generate French TTS and send to CAF via Twilio.
    """
    if not session.twilio_ws or not session.twilio_stream_sid:
        logger.error(f"[{session.call_id}] No Twilio connection")
        return

    logger.info(f"[{session.call_id}] Speaking to CAF: {french_text[:50]}...")
    session.phase = CallPhase.USER_SPEAKING
    await notify_frontend(session, "speaking_to_caf", {"text": french_text})

    try:
        client = gradium.client.GradiumClient(api_key=settings.gradium_api_key)

        tts_stream = await client.tts_stream(
            setup={
                "voice_id": FRENCH_VOICE_ID,
                "output_format": GRADIUM_TTS_FORMAT,  # ulaw_8000 for Twilio
            },
            text=french_text,
        )

        chunk_count = 0
        total_bytes = 0
        async for chunk in tts_stream.iter_bytes():
            chunk_count += 1
            total_bytes += len(chunk)
            # Send audio to Twilio (already in correct format)
            await session.twilio_ws.send_json(
                {
                    "event": "media",
                    "streamSid": session.twilio_stream_sid,
                    "media": {"payload": base64.b64encode(chunk).decode()},
                }
            )

        # logger.info(f"[{session.call_id}] Sent {chunk_count} chunks") # Reduced log
        session.phase = CallPhase.CAF_SPEAKING
        await notify_frontend(session, "finished_speaking")

    except Exception as e:
        logger.error(f"[{session.call_id}] TTS error: {e}")
        session.error = str(e)
