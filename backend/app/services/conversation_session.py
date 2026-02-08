"""
Conversation Session Manager

Manages the state of chat conversations, including:
- Message history (user and agent)
- Metadata (timestamps, conversation ID)
- Persistence to disk (conversations.json)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Single message in the conversation"""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationSession:
    """
    Represents a chat conversation history.
    """

    conversation_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    title: Optional[str] = None  # Auto-generated or user-set title
    messages: List[Message] = field(default_factory=list)

    # Metadata
    dify_conversation_id: Optional[str] = None

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add message to history"""
        msg = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(msg)
        self.updated_at = datetime.now()

        # Auto-generate title from first user message if missing
        if not self.title and role == "user":
            self.title = content[:50] + "..." if len(content) > 50 else content

        save_session(self)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses"""
        return {
            "conversation_id": self.conversation_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title": self.title,
            "dify_conversation_id": self.dify_conversation_id,
            "message_count": len(self.messages),
            # Full messages only if requested, but for simplicity we include them here
            # In a real app, we might want a separate "detail" view
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        """Reconstruct session from dict"""
        session = cls(
            conversation_id=data["conversation_id"],
            title=data.get("title"),
            dify_conversation_id=data.get("dify_conversation_id"),
        )

        if "created_at" in data:
            session.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            session.updated_at = datetime.fromisoformat(data["updated_at"])

        if "messages" in data:
            session.messages = [Message.from_dict(m) for m in data["messages"]]

        return session


# In-memory cache backed by file
_conversations: Dict[str, ConversationSession] = {}
CONVERSATIONS_FILE = "conversations.json"


def load_conversations():
    """Load conversations from disk"""
    global _conversations
    if not os.path.exists(CONVERSATIONS_FILE):
        return

    try:
        with open(CONVERSATIONS_FILE, "r") as f:
            data = json.load(f)
            for cid, s_data in data.items():
                try:
                    _conversations[cid] = ConversationSession.from_dict(s_data)
                except Exception as e:
                    logger.error(f"Failed to load conversation {cid}: {e}")
        logger.info(f"Loaded {len(_conversations)} conversations from disk")
    except Exception as e:
        logger.error(f"Error loading conversations: {e}")


def save_all_conversations():
    """Save all conversations to disk"""
    try:
        data = {cid: s.to_dict() for cid, s in _conversations.items()}
        with open(CONVERSATIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving conversations: {e}")


def save_session(session: ConversationSession):
    """Save single session"""
    _conversations[session.conversation_id] = session
    save_all_conversations()


# Load on module import
load_conversations()


def create_conversation(dify_id: str = None) -> ConversationSession:
    """Create a new conversation session"""
    conv_id = str(uuid.uuid4())
    session = ConversationSession(conversation_id=conv_id, dify_conversation_id=dify_id)
    save_session(session)
    logger.info(f"Created conversation {conv_id}")
    return session


def get_conversation(conv_id: str) -> Optional[ConversationSession]:
    """Get conversation by ID"""
    return _conversations.get(conv_id)


def delete_conversation(conv_id: str):
    """Remove conversation from store"""
    if conv_id in _conversations:
        del _conversations[conv_id]
        save_all_conversations()
        logger.info(f"Deleted conversation {conv_id}")


def list_conversations() -> List[ConversationSession]:
    """List all active conversations"""
    return sorted(_conversations.values(), key=lambda s: s.updated_at, reverse=True)
