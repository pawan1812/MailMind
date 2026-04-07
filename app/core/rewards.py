"""RewardCalculator — Dense, interpretable, 12 sub-components, capped ±0.5/step.

Every step() call triggers reward computation. Each of the 12 named components
independently signals agent performance so the reward is never sparse.

Reward Properties:
  - Dense: every action type generates signal (no zero-information steps)
  - Interpretable: each component maps to a human-understandable criterion
  - Bounded: total per-step reward clamped to [-0.5, +0.5]
  - Proportional: partial credit for partially-correct decisions
"""

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
    """Word-overlap + bigram Jaccard fallback when sentence-transformers is unavailable."""
    words_a = a.lower().split()
    words_b = b.lower().split()
    if not words_a or not words_b:
        return 0.0

    # Unigram overlap
    set_a, set_b = set(words_a), set(words_b)
    unigram_sim = len(set_a & set_b) / max(len(set_a), len(set_b))

    # Bigram overlap (captures phrase-level similarity)
    bigrams_a = set(zip(words_a, words_a[1:])) if len(words_a) > 1 else set()
    bigrams_b = set(zip(words_b, words_b[1:])) if len(words_b) > 1 else set()
    bigram_sim = 0.0
    if bigrams_a and bigrams_b:
        bigram_sim = len(bigrams_a & bigrams_b) / max(len(bigrams_a), len(bigrams_b))

    # Length penalty: replies that are too short are penalized
    len_ratio = min(len(words_a), len(words_b)) / max(len(words_a), len(words_b))
    length_bonus = 0.1 if 0.4 <= len_ratio <= 2.5 else -0.1

    return min(1.0, unigram_sim * 0.5 + bigram_sim * 0.3 + length_bonus * 0.2 + 0.05)


# Professional reply quality keywords by category
_QUALITY_KEYWORDS = {
    'meeting_request': {'available', 'confirm', 'schedule', 'time', 'meeting', 'discuss'},
    'action_required': {'review', 'feedback', 'deadline', 'will', 'complete', 'attached'},
    'complaint': {'apologize', 'understand', 'resolve', 'escalate', 'sorry', 'investigate'},
    'approval_needed': {'approve', 'approved', 'review', 'budget', 'proceed', 'confirm'},
    'legal': {'acknowledge', 'review', 'sign', 'deadline', 'document', 'compliance'},
    'invoice': {'payment', 'process', 'receipt', 'amount', 'scheduled', 'received'},
}


class RewardCalculator:
    """Computes dense reward for every step based on action and episode state.

    12 components ensure the agent always receives a meaningful gradient signal:
      1. classification_accuracy:    ±0.20 for priority+category correctness
      2. reply_relevance:            -0.10..+0.40 for content similarity to reference
      3. tone_match:                 +0.10 for correct formality level
      4. timeliness_bonus:           +0.05..+0.15 for replying to deadlined emails
      5. archive_correctness:        ±0.15 for archive/no-archive decision
      6. flag_correctness:           +0.10 for flagging VIP/legal emails
      7. followup_quality:           ±0.15 for scheduling within expected window
      8. injection_response:         +0.20 for handling urgent mid-episode emails
      9. wrong_delete_penalty:       -0.30 for deleting important emails
     10. redundant_action_penalty:   -0.05 for repeating already-processed emails
     11. missed_deadline_penalty:    -0.15 for skipping deadlined emails
     12. step_waste_penalty:         -0.01 for skipping without reason
    """

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
                # Skipping an email with a deadline is worse than skipping a normal one
                if gt.get('deadline_hint'):
                    bd.missed_deadline_penalty = -0.15

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
        """±0.20: full credit for both correct, partial for one, negative for total miss."""
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
        """-0.10..+0.40: semantic or keyword-based similarity to reference reply."""
        ref = gt.get('reference_reply')
        if not ref or not action.reply_body:
            return 0.0

        # Try semantic similarity first (more accurate)
        model = _get_sem_model()
        if model is not None:
            emb_a = model.encode(action.reply_body, convert_to_tensor=True)
            emb_r = model.encode(ref, convert_to_tensor=True)
            sim = float(st_util.cos_sim(emb_a, emb_r))
        else:
            sim = _basic_similarity(action.reply_body, ref)

        # Bonus: check for domain-specific quality keywords
        category = gt.get('category', '')
        keywords = _QUALITY_KEYWORDS.get(category, set())
        reply_lower = action.reply_body.lower()
        keyword_hits = sum(1 for kw in keywords if kw in reply_lower)
        keyword_bonus = min(0.05, keyword_hits * 0.01)  # max +0.05

        # Length quality: too-short replies are penalized
        word_count = len(action.reply_body.split())
        if word_count < 5:
            length_penalty = -0.05
        elif word_count > 200:
            length_penalty = -0.02  # Over-verbose
        else:
            length_penalty = 0.0

        base_reward = self._sim_to_reward(sim)
        return max(-0.10, min(0.40, base_reward + keyword_bonus + length_penalty))

    @staticmethod
    def _sim_to_reward(sim: float) -> float:
        """Convert similarity score to reward value with graduated thresholds."""
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
        """+0.10 if the reply tone matches the expected formality for the sender role."""
        return 0.10 if action.tone == gt.get('expected_tone') else 0.0

    def _timeliness_reward(self, em_id: str, ep: EpisodeState) -> float:
        """+0.05..+0.15: higher reward for replying to time-sensitive emails."""
        gt = ep.ground_truth.get(em_id, {})
        if gt.get('deadline_hint'):
            return 0.15
        return 0.05

    def _archive_reward(self, em_id: str, gt: dict) -> float:
        """±0.15: positive for correct archive, negative for archiving important emails."""
        should = gt.get('should_archive', False)
        return 0.10 if should else -0.15

    def _flag_reward(self, action: Action, gt: dict) -> float:
        """+0.10 for correctly flagging important emails, -0.05 for false flags."""
        if gt.get('should_flag'):
            return 0.10
        return -0.05 if action.flag_reason else 0.0

    def _followup_reward(self, action: Action, gt: dict) -> float:
        """±0.15: within expected window is positive, outside is negative."""
        ok_range = gt.get('followup_days_range', (1, 7))
        if ok_range == (0, 0):
            return -0.05  # Scheduling followup on a non-followup email
        d = action.followup_days or 0
        if ok_range[0] <= d <= ok_range[1]:
            return 0.15
        # Partial credit for being close
        distance = min(abs(d - ok_range[0]), abs(d - ok_range[1]))
        if distance <= 2:
            return 0.05
        return -0.05

    def _delete_reward(self, em_id: str, gt: dict) -> float:
        """Positive for deleting spam/newsletters, harsh penalty for deleting important."""
        is_junk = gt.get('category') in ('spam', 'newsletter')
        if is_junk:
            return 0.10  # Correct: reward deleting junk
        # Harsh penalty scales with importance
        if gt.get('priority') in ('urgent', 'high'):
            return -0.30
        return -0.20

    def _build_reason(self, bd: RewardBreakdown, action: Action) -> str:
        parts = []
        d = vars(bd)
        for k, v in d.items():
            if v != 0.0:
                parts.append(f"{k}: {v:+.2f}")
        if not parts:
            return f"{action.action_type}: no reward delta"
        return f"{action.action_type}: {', '.join(parts)}"
