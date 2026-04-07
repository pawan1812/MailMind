"""Observation, Email, Thread, InboxSummary — OpenEnv compliant typed models.

These Pydantic v2 models define the complete observation space returned by
reset() and step(). Every field is typed and documented so agents can
programmatically inspect what information is available.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal, Dict
from datetime import datetime
import uuid

SenderImportance = Literal[
    'ceo', 'vip', 'direct_manager', 'colleague',
    'external_client', 'vendor', 'unknown', 'spam_likely'
]

Priority = Literal['urgent', 'high', 'medium', 'low']

Category = Literal[
    'meeting_request', 'action_required', 'fyi',
    'newsletter', 'spam', 'invoice', 'hr', 'legal',
    'personal', 'complaint', 'approval_needed', 'other'
]

class ThreadMessage(BaseModel):
    """A single message within an email thread."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender: str
    sent_at: datetime
    body: str
    is_read: bool = False

class EmailThread(BaseModel):
    """A conversation thread containing multiple messages."""
    thread_id: str
    subject: str
    participants: List[str]
    messages: List[ThreadMessage]
    message_count: int

class Email(BaseModel):
    """A single email in the inbox — the core observation unit.

    Contains all information an agent needs to decide what action to take:
    sender identity and importance, full body text, thread context,
    deadline hints, and attachment metadata.
    """
    email_id: str
    subject: str
    sender: str
    sender_email: str
    sender_domain: str
    sender_importance: SenderImportance
    body: str
    received_at: datetime
    has_attachment: bool = False
    attachment_hint: Optional[str] = None
    thread: Optional[EmailThread] = None
    deadline_hint: Optional[str] = None
    cc_count: int = 0
    is_reply_to: Optional[str] = None
    injected: bool = False

    @field_validator('body')
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Email body cannot be empty')
        return v

class InboxSummary(BaseModel):
    """High-level inbox statistics shown to the agent each step."""
    total_emails: int
    unread_count: int
    flagged_count: int = 0
    processed_count: int = 0
    injections_pending: int = 0
    categories: Dict[str, int] = {}
    step_budget_remaining: int = 0
    urgent_count: int = 0
    high_priority_count: int = 0

class Observation(BaseModel):
    """Full OpenEnv-compliant observation returned by reset() and step().

    The observation provides the agent with:
    - Current email to process (with full context)
    - Inbox-level statistics
    - History of recent actions and their rewards
    - Episode progress and termination status
    """
    episode_id: str
    task_id: str = 'classify_inbox'
    step: int
    current_email: Optional[Email] = None
    inbox_summary: InboxSummary
    recent_actions: List[str] = []
    episode_score: float = 0.0
    done: bool = False
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
