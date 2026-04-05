"""EpisodeState — all mutable state for a single episode. PRD §8.1."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set
from datetime import datetime
from app.models.observation import Email
import uuid

@dataclass
class EpisodeState:
    """All mutable state for a single episode."""

    # Identity
    episode_id: str = ""
    session_id: str = "default"
    task_id: str = "classify_inbox"
    inbox_seed: int = 42
    max_steps: int = 20

    # Progress
    step: int = 0
    done: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Inbox
    inbox: List[Email] = field(default_factory=list)
    current_idx: int = 0

    # Agent Decisions
    classifications: Dict[str, dict] = field(default_factory=dict)
    drafts: Dict[str, dict] = field(default_factory=dict)
    archives: List[str] = field(default_factory=list)
    deletions: List[str] = field(default_factory=list)
    flags: Dict[str, str] = field(default_factory=dict)
    followups: Dict[str, dict] = field(default_factory=dict)
    processed_emails: Set[str] = field(default_factory=set)
    redundant_actions: int = 0

    # Dynamic Injection (hard task)
    injected_emails: Set[str] = field(default_factory=set)
    injection_handled: Set[str] = field(default_factory=set)

    # Ground Truth (set at reset, used by grader)
    ground_truth: Dict[str, dict] = field(default_factory=dict)

    # Reward tracking
    cumulative_reward: float = 0.0
    reward_breakdown_acc: Dict[str, float] = field(default_factory=lambda: {
        'classification_reward': 0.0, 'reply_reward': 0.0,
        'archive_reward': 0.0, 'followup_reward': 0.0,
        'injection_reward': 0.0, 'penalty_total': 0.0
    })

    # Audit log
    action_log: List[dict] = field(default_factory=list)
    recent_actions_desc: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.episode_id:
            self.episode_id = f"ep_{uuid.uuid4().hex[:8]}"

    def current_email(self) -> Optional[Email]:
        if self.current_idx < len(self.inbox):
            return self.inbox[self.current_idx]
        return None

    def advance(self):
        self.current_idx += 1

    def is_terminal(self) -> bool:
        return self.step >= self.max_steps or self.current_idx >= len(self.inbox)
