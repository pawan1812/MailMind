"""Reward model — PRD §6.3 compliant. Dense, interpretable, 12 sub-components."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class RewardBreakdown(BaseModel):
    """Named sub-reward components for interpretability."""
    classification_accuracy: float = 0.0
    reply_relevance: float = 0.0
    tone_match: float = 0.0
    timeliness_bonus: float = 0.0
    archive_correctness: float = 0.0
    flag_correctness: float = 0.0
    followup_quality: float = 0.0
    injection_response: float = 0.0
    wrong_delete_penalty: float = 0.0
    redundant_action_penalty: float = 0.0
    missed_deadline_penalty: float = 0.0
    step_waste_penalty: float = 0.0

class Reward(BaseModel):
    """OpenEnv-compliant reward — returned with every step() call."""
    value: float
    cumulative: float
    breakdown: RewardBreakdown
    reason: str
    step: int

class StepResponse(BaseModel):
    """Full response from POST /step endpoint."""
    observation: Optional[Any] = None
    reward: Reward
    done: bool
    info: Dict[str, Any] = {}

class GraderResult(BaseModel):
    """Response from POST /grader."""
    episode_id: str
    task_id: str
    final_score: float
    component_scores: Dict[str, float] = {}
    weighted_scores: Dict[str, float] = {}
    penalties: Dict[str, float] = {}
    total_steps_used: int = 0
    step_budget: int = 0
    efficiency_ratio: float = 0.0
