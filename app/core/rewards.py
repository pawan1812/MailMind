"""RewardCalculator — PRD §9. Dense, interpretable, 12 sub-components, capped ±0.5/step."""

from app.models.action import Action
from app.models.reward import Reward, RewardBreakdown
from app.core.episode import EpisodeState

# Optional sentence-transformers for semantic similarity
try:
    from sentence_transformers import SentenceTransformer, util as st_util
    _HAS_ST = True
except ImportError:
    _HAS_ST = False

_sem_model = None

def _get_sem_model():
    global _sem_model
    if not _HAS_ST:
        return None
    if _sem_model is None:
        _sem_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _sem_model

def _basic_similarity(a: str, b: str) -> float:
    """Word-overlap fallback when sentence-transformers is not installed."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / max(len(words_a), len(words_b))


class RewardCalculator:
    """Computes dense reward for every step based on action and episode state."""

    def compute(self, action: Action, ep: EpisodeState) -> Reward:
        bd = RewardBreakdown()
        current = ep.current_email()
        em_id = action.email_id or (current.email_id if current else 'unknown')
        gt = ep.ground_truth.get(em_id, {})

        match action.action_type:
            case 'classify_email':
                bd.classification_accuracy = self._classify_reward(action, gt)

            case 'draft_reply':
                bd.reply_relevance = self._reply_reward(action, gt)
                bd.tone_match = self._tone_reward(action, gt)

            case 'send_reply':
                bd.timeliness_bonus = self._timeliness_reward(em_id, ep)

            case 'archive':
                bd.archive_correctness = self._archive_reward(em_id, gt)

            case 'flag':
                bd.flag_correctness = self._flag_reward(action, gt)

            case 'schedule_followup':
                bd.followup_quality = self._followup_reward(action, gt)

            case 'skip':
                bd.step_waste_penalty = -0.01

            case 'delete':
                bd.wrong_delete_penalty = self._delete_reward(em_id, gt)

        # Redundant action penalty
        if em_id in ep.processed_emails and action.action_type not in ('skip', 'flag'):
            bd.redundant_action_penalty = -0.05

        # Injection handling bonus
        if em_id in ep.injected_emails and em_id not in ep.injection_handled:
            if action.action_type in ('classify_email', 'draft_reply', 'send_reply'):
                bd.injection_response = 0.20
                ep.injection_handled.add(em_id)

        total = sum(vars(bd).values())
        capped = max(-0.5, min(0.5, total))

        reason = self._build_reason(bd, action)

        return Reward(
            value=round(capped, 4),
            cumulative=round(ep.cumulative_reward + capped, 4),
            breakdown=bd,
            reason=reason,
            step=ep.step,
        )

    def _classify_reward(self, action: Action, gt: dict) -> float:
        if not gt:
            return 0.0
        p_ok = action.priority == gt.get('priority')
        c_ok = action.category == gt.get('category')
        if p_ok and c_ok:
            return 0.20
        if p_ok or c_ok:
            return 0.10
        return -0.10

    def _reply_reward(self, action: Action, gt: dict) -> float:
        ref = gt.get('reference_reply')
        if not ref or not action.reply_body:
            return 0.0

        model = _get_sem_model()
        if model is not None:
            emb_a = model.encode(action.reply_body, convert_to_tensor=True)
            emb_r = model.encode(ref, convert_to_tensor=True)
            sim = float(st_util.cos_sim(emb_a, emb_r))
        else:
            sim = _basic_similarity(action.reply_body, ref)

        if sim >= 0.85:
            return 0.40
        elif sim >= 0.70:
            return 0.28
        elif sim >= 0.50:
            return 0.16
        elif sim >= 0.30:
            return 0.06
        else:
            return -0.10

    def _tone_reward(self, action: Action, gt: dict) -> float:
        return 0.10 if action.tone == gt.get('expected_tone') else 0.0

    def _timeliness_reward(self, em_id: str, ep: EpisodeState) -> float:
        gt = ep.ground_truth.get(em_id, {})
        if gt.get('deadline_hint'):
            return 0.15
        return 0.05

    def _archive_reward(self, em_id: str, gt: dict) -> float:
        should = gt.get('should_archive', False)
        return 0.10 if should else -0.15

    def _flag_reward(self, action: Action, gt: dict) -> float:
        return 0.10 if gt.get('should_flag') else 0.0

    def _followup_reward(self, action: Action, gt: dict) -> float:
        ok_range = gt.get('followup_days_range', (1, 7))
        d = action.followup_days or 0
        if ok_range[0] <= d <= ok_range[1]:
            return 0.15
        return -0.05

    def _delete_reward(self, em_id: str, gt: dict) -> float:
        is_junk = gt.get('category') in ('spam', 'newsletter')
        return 0.0 if is_junk else -0.30

    def _build_reason(self, bd: RewardBreakdown, action: Action) -> str:
        parts = []
        d = vars(bd)
        for k, v in d.items():
            if v != 0.0:
                parts.append(f"{k}: {v:+.2f}")
        if not parts:
            return f"{action.action_type}: no reward delta"
        return f"{action.action_type}: {', '.join(parts)}"
