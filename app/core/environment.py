"""MailMindEnv — Core environment class implementing the OpenEnv spec.

Implements the standard OpenEnv interface:
  - reset(task_id, seed) → Observation
  - step(action)         → StepResponse(observation, reward, done, info)
  - state()              → Current episode state dict
  - grade()              → GraderResult with score in (0.0, 1.0)

The environment simulates enterprise email management across three difficulty
levels.  State is fully encapsulated in EpisodeState so reset() always produces
a clean slate.
"""

import uuid
from typing import Optional, Dict
from app.core.episode import EpisodeState
from app.core.inbox import InboxSimulator
from app.core.rewards import RewardCalculator
from app.core.injection import DynamicInjector
from app.models.observation import Observation, InboxSummary
from app.models.action import Action
from app.models.reward import Reward, StepResponse, GraderResult

# Task configs
TASK_CONFIGS = {
    'classify_inbox': {'max_steps': 20, 'inbox_size': 15, 'default_seed': 42},
    'draft_replies':  {'max_steps': 30, 'inbox_size': 25, 'default_seed': 42},
    'manage_inbox':   {'max_steps': 60, 'inbox_size': 40, 'default_seed': 42},
}

# Grader weights per task
GRADER_WEIGHTS = {
    'classify_inbox': {'classification': 1.0},
    'draft_replies':  {'classification': 0.40, 'reply': 0.60},
    'manage_inbox':   {'classification': 0.30, 'reply': 0.30, 'archive': 0.15,
                       'followup': 0.15, 'injection': 0.10},
}


class MailMindEnv:
    """Core OpenEnv environment. One instance per session.

    Thread-safety: each session gets its own MailMindEnv instance via the
    session pool in dependencies.py. No shared mutable state across sessions.
    """

    def __init__(self, session_id: str = 'default'):
        self.session_id = session_id
        self.episode: Optional[EpisodeState] = None
        self.reward_calc = RewardCalculator()
        self.injector = DynamicInjector()

    def reset(self, task_id: str = 'classify_inbox', seed: Optional[int] = None) -> Observation:
        """Start a fresh episode.

        Args:
            task_id: One of 'classify_inbox', 'draft_replies', 'manage_inbox'
            seed: Random seed for deterministic inbox generation

        Returns:
            Initial observation with first email to process
        """
        config = TASK_CONFIGS.get(task_id)
        if not config:
            raise ValueError(f"Unknown task: {task_id}. Must be one of {list(TASK_CONFIGS.keys())}")

        inbox_seed = seed if seed is not None else config['default_seed']

        self.episode = EpisodeState(
            session_id=self.session_id,
            task_id=task_id,
            inbox_seed=inbox_seed,
            max_steps=config['max_steps'],
        )

        sim = InboxSimulator(seed=inbox_seed)
        inbox, ground_truth = sim.generate(task_id)
        self.episode.inbox = inbox
        self.episode.ground_truth = ground_truth

        return self._build_observation()

    def step(self, action: Action) -> StepResponse:
        """Process one agent action.

        Args:
            action: Typed Action with action_type and relevant fields

        Returns:
            StepResponse with observation, reward, done flag, and info dict
        """
        if self.episode is None:
            raise RuntimeError('Call reset() before step()')
        if self.episode.done:
            raise RuntimeError('Episode is done. Call reset() to start a new one.')

        current = self.episode.current_email()
        em_id = action.email_id or (current.email_id if current else 'unknown')

        # 1. Compute reward
        reward = self.reward_calc.compute(action, self.episode)

        # 2. Apply action to episode state
        self._apply_action(action, reward, em_id)

        # 3. Increment step
        self.episode.step += 1

        # 4. Dynamic injection (hard task)
        injected = self.injector.check_and_inject(self.episode)
        env_msg = f'[URGENT INJECTION] New email arrived: {injected.subject}' if injected else None

        # 5. Check termination
        if self.episode.is_terminal():
            self.episode.done = True

        # 6. Advance to next email if current processed
        if self._email_fully_processed(action, em_id):
            self.episode.advance()

        # Double-check termination after advance
        if self.episode.current_email() is None:
            self.episode.done = True

        obs = self._build_observation(message=env_msg)
        return StepResponse(
            observation=obs.model_dump() if not self.episode.done else None,
            reward=reward,
            done=self.episode.done,
            info={
                'step': self.episode.step,
                'budget_remaining': self.episode.max_steps - self.episode.step,
                'emails_processed': len(self.episode.processed_emails),
                'emails_total': len(self.episode.inbox),
            }
        )

    def state(self) -> dict:
        """Return current episode state for debugging and monitoring."""
        if self.episode is None:
            return {'status': 'no_active_episode'}
        ep = self.episode
        return {
            'episode_id': ep.episode_id,
            'task_id': ep.task_id,
            'step': ep.step,
            'max_steps': ep.max_steps,
            'done': ep.done,
            'cumulative_reward': ep.cumulative_reward,
            'classifications': ep.classifications,
            'drafts_count': len(ep.drafts),
            'archives_count': len(ep.archives),
            'deletions_count': len(ep.deletions),
            'flags_count': len(ep.flags),
            'followups_count': len(ep.followups),
            'processed_count': len(ep.processed_emails),
            'redundant_actions': ep.redundant_actions,
            'injected_count': len(ep.injected_emails),
            'injection_handled_count': len(ep.injection_handled),
        }

    def grade(self) -> GraderResult:
        """Grade the current episode using task-specific modular graders.

        Returns a GraderResult with:
        - final_score in [0.0, 1.0]
        - component_scores per grading dimension
        - weighted_scores showing contribution to final
        - penalties deducted
        - episode_bonuses earned
        """
        if self.episode is None:
            raise RuntimeError('No episode to grade')

        ep = self.episode
        gt = ep.ground_truth

        # Use modular graders (preferred — they have richer output)
        from app.core.graders import GRADERS
        grader_cls = GRADERS.get(ep.task_id)
        if grader_cls:
            grader = grader_cls()
            grader_result = grader.grade(ep)
        else:
            grader_result = {'score': 0.0}

        # Compute component scores via inline methods (for GraderResult structure)
        weights = GRADER_WEIGHTS.get(ep.task_id, GRADER_WEIGHTS['classify_inbox'])

        cls_score = self._grade_classifications(ep, gt)
        reply_score = self._grade_replies(ep, gt)
        archive_score = self._grade_archives(ep, gt)
        followup_score = self._grade_followups(ep, gt)
        injection_score = self._grade_injections(ep)

        component_scores = {
            'classification': round(cls_score, 4),
            'reply': round(reply_score, 4),
            'archive': round(archive_score, 4),
            'followup': round(followup_score, 4),
            'injection': round(injection_score, 4),
        }

        weighted = {}
        final = 0.0
        for k, v in component_scores.items():
            w = weights.get(k, 0.0)
            weighted[k] = round(v * w, 4)
            final += v * w

        # Penalties
        waste_pen = min(0.10, ep.redundant_actions * 0.02)
        missed = sum(1 for eid, g in gt.items()
                     if g.get('deadline_hint') and eid not in ep.processed_emails)
        deadline_pen = min(0.10, missed * 0.02)
        wrong_del = [d for d in ep.deletions
                     if gt.get(d, {}).get('category') not in ('spam', 'newsletter')]
        delete_pen = min(0.15, len(wrong_del) * 0.05)

        penalties = {
            'redundant_steps': round(waste_pen, 4),
            'missed_deadlines': round(deadline_pen, 4),
            'wrong_deletes': round(delete_pen, 4),
        }

        # Episode bonuses
        completion = len(ep.processed_emails) / len(ep.inbox) if ep.inbox else 0
        bonus = 0.0
        episode_bonuses = {}
        if completion >= 0.95:
            bonus += 0.05
            episode_bonuses['inbox_completion'] = 0.05
        if not wrong_del:
            bonus += 0.02
            episode_bonuses['zero_wrong_deletes'] = 0.02
        if ep.step < ep.max_steps * 0.7 and completion >= 0.90:
            bonus += 0.03
            episode_bonuses['time_efficiency'] = 0.03
        episode_bonuses['total_bonus'] = round(bonus, 4)

        total_penalty = waste_pen + deadline_pen + delete_pen
        # Clamp to open interval (0, 1) — bounds survive :.2f formatting
        final_score = max(0.01, min(0.99, final + bonus - total_penalty))

        return GraderResult(
            episode_id=ep.episode_id,
            task_id=ep.task_id,
            final_score=round(final_score, 4),
            component_scores=component_scores,
            weighted_scores=weighted,
            penalties=penalties,
            episode_bonuses=episode_bonuses,
            total_steps_used=ep.step,
            step_budget=ep.max_steps,
            efficiency_ratio=round(ep.step / ep.max_steps, 4) if ep.max_steps > 0 else 0.0,
        )

    # ── Private helpers ──────────────────────────────────────────────

    def _apply_action(self, action: Action, reward: Reward, em_id: str):
        ep = self.episode

        if em_id in ep.processed_emails and action.action_type not in ('skip', 'flag', 'draft_reply'):
            ep.redundant_actions += 1

        match action.action_type:
            case 'classify_email':
                ep.classifications[em_id] = {
                    'priority': action.priority, 'category': action.category
                }
                ep.processed_emails.add(em_id)
            case 'draft_reply':
                ep.drafts[em_id] = {
                    'body': action.reply_body, 'tone': action.tone, 'sent': False,
                    'step_drafted': ep.step
                }
            case 'send_reply':
                if em_id in ep.drafts:
                    ep.drafts[em_id]['sent'] = True
                ep.processed_emails.add(em_id)
            case 'archive':
                ep.archives.append(em_id)
                ep.processed_emails.add(em_id)
            case 'delete':
                ep.deletions.append(em_id)
                ep.processed_emails.add(em_id)
            case 'flag':
                ep.flags[em_id] = action.flag_reason or 'needs_review'
            case 'schedule_followup':
                ep.followups[em_id] = {
                    'days': action.followup_days, 'note': action.followup_note
                }
                ep.processed_emails.add(em_id)

        ep.action_log.append({
            'step': ep.step, 'action': action.action_type,
            'email_id': em_id, 'reward': reward.value
        })
        ep.cumulative_reward = round(ep.cumulative_reward + reward.value, 4)

        desc = f"Step {ep.step}: {action.action_type} on {em_id} → reward {reward.value:+.3f}"
        ep.recent_actions_desc.append(desc)
        if len(ep.recent_actions_desc) > 5:
            ep.recent_actions_desc = ep.recent_actions_desc[-5:]

    def _email_fully_processed(self, action: Action, em_id: str) -> bool:
        simple_advance = ('archive', 'delete', 'skip', 'send_reply', 'schedule_followup')
        if action.action_type in simple_advance:
            return True
        if action.action_type == 'classify_email':
            gt = self.episode.ground_truth.get(em_id, {})
            if not gt.get('requires_reply') and gt.get('should_archive'):
                return False  # agent should still archive
            if not gt.get('requires_reply'):
                return True
        return False

    def _build_observation(self, message: str = None) -> Observation:
        ep = self.episode
        current = ep.current_email()

        # Build category counts
        cats: Dict[str, int] = {}
        urgent_count = 0
        high_count = 0
        for em in ep.inbox:
            gt = ep.ground_truth.get(em.email_id, {})
            c = gt.get('category', 'other')
            cats[c] = cats.get(c, 0) + 1
            p = gt.get('priority', 'low')
            if p == 'urgent':
                urgent_count += 1
            elif p == 'high':
                high_count += 1

        inj_pending = len(ep.injected_emails - ep.injection_handled) if ep.task_id == 'manage_inbox' else 0

        summary = InboxSummary(
            total_emails=len(ep.inbox),
            unread_count=len(ep.inbox) - len(ep.processed_emails),
            flagged_count=len(ep.flags),
            processed_count=len(ep.processed_emails),
            injections_pending=inj_pending,
            categories=cats,
            step_budget_remaining=ep.max_steps - ep.step,
            urgent_count=urgent_count,
            high_priority_count=high_count,
        )

        return Observation(
            episode_id=ep.episode_id,
            task_id=ep.task_id,
            step=ep.step,
            current_email=current,
            inbox_summary=summary,
            recent_actions=ep.recent_actions_desc[-5:],
            episode_score=ep.cumulative_reward,
            done=ep.done,
            message=message,
        )

    def _grade_classifications(self, ep: EpisodeState, gt: dict) -> float:
        total = len(gt)
        if total == 0:
            return 0.01
        score = 0.0
        for eid, truth in gt.items():
            pred = ep.classifications.get(eid)
            if not pred:
                continue
            if pred['priority'] == truth['priority']:
                score += 0.4
            if pred['category'] == truth['category']:
                score += 0.6
        return score / total

    def _grade_replies(self, ep: EpisodeState, gt: dict) -> float:
        reply_needed = [eid for eid, g in gt.items() if g.get('requires_reply')]
        if not reply_needed:
            return 0.99
        score = 0.0
        for eid in reply_needed:
            draft = ep.drafts.get(eid)
            if draft and draft.get('sent'):
                score += 0.7  # sent a reply
                if draft.get('tone') == gt[eid].get('expected_tone'):
                    score += 0.3
            elif draft:
                score += 0.3  # drafted but not sent
        return score / len(reply_needed)

    def _grade_archives(self, ep: EpisodeState, gt: dict) -> float:
        should = {eid for eid, g in gt.items() if g.get('should_archive')}
        if not should:
            return 0.99
        correct = len(set(ep.archives) & should)
        false_arch = len(set(ep.archives) - should)
        return max(0.0, (correct - false_arch * 0.5) / len(should))

    def _grade_followups(self, ep: EpisodeState, gt: dict) -> float:
        needed = {eid for eid, g in gt.items() if g.get('needs_followup')}
        if not needed:
            return 0.99
        correct = sum(1 for eid in ep.followups if eid in needed)
        return correct / len(needed)

    def _grade_injections(self, ep: EpisodeState) -> float:
        if not ep.injected_emails:
            return 0.99
        handled = ep.injection_handled & ep.injected_emails
        return len(handled) / len(ep.injected_emails)
