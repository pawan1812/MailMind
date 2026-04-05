"""Action model — PRD §6.2 compliant. 8 distinct action types."""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal

ActionType = Literal[
    'classify_email',
    'draft_reply',
    'send_reply',
    'archive',
    'delete',
    'flag',
    'schedule_followup',
    'skip',
]

class Action(BaseModel):
    """OpenEnv-compliant action submitted to step()."""
    action_type: ActionType

    # classify_email
    priority: Optional[Literal['urgent', 'high', 'medium', 'low']] = None
    category: Optional[Literal[
        'meeting_request', 'action_required', 'fyi', 'newsletter',
        'spam', 'invoice', 'hr', 'legal', 'personal',
        'complaint', 'approval_needed', 'other']] = None

    # draft_reply / send_reply
    email_id: Optional[str] = None
    reply_body: Optional[str] = Field(None, max_length=2000)
    tone: Optional[Literal['formal', 'friendly', 'assertive']] = None

    # schedule_followup
    followup_days: Optional[int] = Field(None, ge=1, le=30)
    followup_note: Optional[str] = Field(None, max_length=200)

    # flag
    flag_reason: Optional[Literal[
        'awaiting_reply', 'vip', 'legal', 'urgent', 'needs_review']] = None

    @model_validator(mode='after')
    def validate_required_fields(self) -> 'Action':
        if self.action_type == 'classify_email':
            if not self.priority or not self.category:
                raise ValueError('classify_email requires priority AND category')
        if self.action_type in ('draft_reply', 'send_reply'):
            if not self.email_id:
                raise ValueError(f'{self.action_type} requires email_id')
        if self.action_type == 'draft_reply' and not self.reply_body:
            raise ValueError('draft_reply requires reply_body')
        return self
