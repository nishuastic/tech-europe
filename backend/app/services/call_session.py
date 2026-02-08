"""
Call Session Manager

Manages the state of interactive call sessions, including:
- Pre-call info gathering
- Live call phase tracking
- WebSocket connections (frontend + Twilio)
- Audio queues for bidirectional streaming
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
import asyncio
import uuid
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)


class CallPhase(Enum):
    """Phases of an interactive call session"""

    GATHERING_INFO = "gathering_info"  # Collecting CAF number, name, etc.
    READY_TO_CALL = "ready_to_call"  # Info gathered, ready to dial
    DIALING = "dialing"  # Call initiated, waiting for pickup
    CONNECTED = "connected"  # Call connected
    WAITING_GREETING_RESPONSE = (
        "waiting_greeting_response"  # Said Bonjour, waiting for CAF
    )
    CAF_SPEAKING = "caf_speaking"  # CAF agent is talking
    WAITING_USER = "waiting_user"  # Waiting for user to respond
    USER_SPEAKING = "user_speaking"  # Playing user's response to CAF
    ENDED = "ended"  # Call completed
    FAILED = "failed"  # Call failed


@dataclass
class TranscriptEntry:
    """Single entry in the call transcript"""

    speaker: str  # "caf" or "user"
    french_text: str
    english_text: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        return {
            "speaker": self.speaker,
            "french_text": self.french_text,
            "english_text": self.english_text,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CallSession:
    """
    Represents an interactive call session.
    """

    call_id: str
    phase: CallPhase = CallPhase.GATHERING_INFO
    created_at: datetime = field(default_factory=datetime.now)

    # Pre-call info (gathered from user)
    target: str = "caf"  # caf, prefecture, impots
    caf_number: Optional[str] = None
    user_name: Optional[str] = None
    user_question: Optional[str] = None

    # Call identifiers
    twilio_call_sid: Optional[str] = None
    twilio_stream_sid: Optional[str] = None

    # Transcript
    transcript: List[TranscriptEntry] = field(default_factory=list)

    # WebSocket references (set at runtime - NOT PERSISTED)
    frontend_ws: Optional[Any] = None
    twilio_ws: Optional[Any] = None

    # Audio queues for async streaming (NOT PERSISTED)
    to_caf_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    from_caf_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    # Error tracking
    error: Optional[str] = None

    # Dify conversation ID
    dify_conversation_id: Optional[str] = None

    def is_info_complete(self) -> bool:
        """Check if we have all required info to make the call"""
        return all(
            [
                self.user_question,
            ]
        )

    def add_transcript(self, speaker: str, french: str, english: str):
        """Add entry to transcript"""
        entry = TranscriptEntry(
            speaker=speaker,
            french_text=french,
            english_text=english,
        )
        self.transcript.append(entry)
        save_session(self)  # Auto-save on transcript update
        logger.info(f"[{self.call_id}] {speaker}: {english[:50]}...")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses"""
        return {
            "call_id": self.call_id,
            "phase": self.phase.value,
            "target": self.target,
            "caf_number": self.caf_number,
            "user_name": self.user_name,
            "user_question": self.user_question,
            "twilio_call_sid": self.twilio_call_sid,
            "transcript": [t.to_dict() for t in self.transcript],
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallSession":
        """Reconstruct session from dict (for loading)"""
        session = cls(
            call_id=data["call_id"],
            target=data.get("target", "caf"),
            caf_number=data.get("caf_number"),
            user_name=data.get("user_name"),
            user_question=data.get("user_question"),
            twilio_call_sid=data.get("twilio_call_sid"),
            error=data.get("error"),
            dify_conversation_id=data.get("dify_conversation_id"),
        )
        if "phase" in data:
            try:
                session.phase = CallPhase(data["phase"])
            except ValueError:
                session.phase = CallPhase.ENDED

        if "created_at" in data:
            session.created_at = datetime.fromisoformat(data["created_at"])

        if "transcript" in data:
            session.transcript = []
            for t_data in data["transcript"]:
                session.transcript.append(
                    TranscriptEntry(
                        speaker=t_data["speaker"],
                        french_text=t_data["french_text"]
                        if "french_text" in t_data
                        else t_data.get("french", ""),
                        english_text=t_data["english_text"]
                        if "english_text" in t_data
                        else t_data.get("english", ""),
                        timestamp=datetime.fromisoformat(t_data["timestamp"])
                        if "timestamp" in t_data
                        else datetime.now(),
                    )
                )

        return session


# In-memory cache backed by file
_sessions: Dict[str, CallSession] = {}


SESSIONS_FILE = "sessions.json"


def load_sessions():
    """Load sessions from disk"""
    global _sessions
    if not os.path.exists(SESSIONS_FILE):
        return

    try:
        with open(SESSIONS_FILE, "r") as f:
            data = json.load(f)
            for cid, s_data in data.items():
                try:
                    _sessions[cid] = CallSession.from_dict(s_data)
                except Exception as e:
                    logger.error(f"Failed to load session {cid}: {e}")
        logger.info(f"Loaded {len(_sessions)} sessions from disk")
    except Exception as e:
        logger.error(f"Error loading sessions: {e}")


def save_all_sessions():
    """Save all sessions to disk"""
    try:
        data = {cid: s.to_dict() for cid, s in _sessions.items()}
        with open(SESSIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving sessions: {e}")


def save_session(session: CallSession):
    """Save single session (trigger full save for simplicity)"""
    _sessions[session.call_id] = session
    save_all_sessions()


# Load on module import
load_sessions()


def create_session(target: str = "caf") -> CallSession:
    """Create a new call session"""
    call_id = str(uuid.uuid4())
    session = CallSession(call_id=call_id, target=target)
    save_session(session)
    logger.info(f"Created session {call_id} for {target}")
    return session


def get_session(call_id: str) -> Optional[CallSession]:
    """Get session by ID"""
    return _sessions.get(call_id)


def delete_session(call_id: str):
    """Remove session from store"""
    if call_id in _sessions:
        del _sessions[call_id]
        save_all_sessions()
        logger.info(f"Deleted session {call_id}")


def list_sessions() -> List[CallSession]:
    """List all active sessions"""
    # Sort by created_at desc
    return sorted(_sessions.values(), key=lambda s: s.created_at, reverse=True)
