"""Grader modules — Per-task deterministic grading logic.

Each grader produces a score in [0.0, 1.0] with a full breakdown explaining
how the score was computed. Graders are DETERMINISTIC: same agent trajectory
on the same seeded episode → identical score.

Grader Architecture:
  ClassifyGrader  → Easy task: priority (60%) + category (40%) accuracy
  ReplyGrader     → Medium task: classify (40%) + draft+send+tone+content (60%)
  WorkflowGrader  → Hard task: 5-component weighted composite + episode bonuses
"""

from app.core.episode import EpisodeState

# Professional reply quality keywords by category
_QUALITY_KEYWORDS = {
    'meeting_request': {'available', 'confirm', 'schedule', 'time', 'meeting', 'discuss', 'calendar'},
    'action_required': {'review', 'feedback', 'deadline', 'will', 'complete', 'attached', 'priority'},
    'complaint': {'apologize', 'understand', 'resolve', 'escalate', 'sorry', 'investigate', 'resolution'},
    'approval_needed': {'approve', 'approved', 'review', 'budget', 'proceed', 'confirm', 'authorization'},
    'legal': {'acknowledge', 'review', 'sign', 'deadline', 'document', 'compliance', 'legal'},
    'invoice': {'payment', 'process', 'receipt', 'amount', 'scheduled', 'received', 'transfer'},
}


class ClassifyGrader:
    """Task 1 — Email Classification (Easy).

    Scoring formula:
        score = (priority_accuracy × 0.6) + (category_accuracy × 0.4)

    An email is counted as priority-correct if the agent's predicted priority
    exactly matches ground truth.  Same for category.  Unclassified emails
    count as incorrect for both dimensions.
    """

    def grade(self, ep: EpisodeState) -> dict:
        gt = ep.ground_truth
        total = len(gt)
        if total == 0:
            return {'score': 0.0, 'breakdown': {}}

        p_correct = 0
        c_correct = 0
        classified_count = 0
        breakdown = {}

        for eid, truth in gt.items():
            pred = ep.classifications.get(eid)
            ok_p = ok_c = False
            if pred:
                classified_count += 1
                ok_p = pred['priority'] == truth['priority']
                ok_c = pred['category'] == truth['category']
                if ok_p:
                    p_correct += 1
                if ok_c:
                    c_correct += 1
            breakdown[eid] = {
                'priority_correct': ok_p,
                'category_correct': ok_c,
                'expected_priority': truth.get('priority'),
                'given_priority': pred.get('priority') if pred else None,
                'expected_category': truth.get('category'),
                'given_category': pred.get('category') if pred else None,
            }

        # Score = (exact priority matches / N) * 0.6 + (exact category matches / N) * 0.4
        score = (p_correct / total) * 0.6 + (c_correct / total) * 0.4

        # Coverage penalty: if agent skipped emails, reduce score
        coverage = classified_count / total
        if coverage < 1.0:
            score *= (0.5 + 0.5 * coverage)  # At 50% coverage → 75% of raw score

        return {
            'score': round(min(1.0, max(0.0, score)), 4),
            'priority_accuracy': round(p_correct / total, 4),
            'category_accuracy': round(c_correct / total, 4),
            'coverage': round(coverage, 4),
            'total_emails': total,
            'classified': classified_count,
            'breakdown': breakdown,
        }


class ReplyGrader:
    """Task 2 — Reply Drafting (Medium).

    Scoring formula per reply-needed email:
        0.0  — no draft
        0.20 — draft exists
        0.50 — draft sent
        +0.20 — correct tone
        +0.10 — reply body has domain-relevant content keywords

    Also includes classification sub-score (40% classify + 60% reply).
    """

    def grade(self, ep: EpisodeState) -> dict:
        gt = ep.ground_truth
        reply_needed = {eid: g for eid, g in gt.items() if g.get('requires_reply')}

        if not reply_needed:
            return {'score': 1.0, 'breakdown': {}}

        # Sub-score: classification quality (blended in)
        cls_sub = ClassifyGrader().grade(ep)

        total_score = 0.0
        breakdown = {}

        for eid, truth in reply_needed.items():
            draft = ep.drafts.get(eid)
            entry = {
                'drafted': False, 'sent': False, 'tone_correct': False,
                'content_quality': 0.0, 'score': 0.0,
            }

            if draft:
                entry['drafted'] = True
                draft_score = 0.20  # Base for having a draft

                if draft.get('sent'):
                    entry['sent'] = True
                    draft_score = 0.50  # Sent reply

                if draft.get('tone') == truth.get('expected_tone'):
                    entry['tone_correct'] = True
                    draft_score += 0.20

                # Content quality: check for domain keywords
                body = (draft.get('body') or '').lower()
                cat = truth.get('category', '')
                keywords = _QUALITY_KEYWORDS.get(cat, set())
                hits = sum(1 for kw in keywords if kw in body)
                content_bonus = min(0.10, hits * 0.02)
                entry['content_quality'] = round(content_bonus, 2)
                draft_score += content_bonus

                # Length check: too-short replies are penalized
                if body and len(body.split()) < 3:
                    draft_score -= 0.05

                entry['score'] = round(min(1.0, max(0.0, draft_score)), 2)
                total_score += entry['score']

            breakdown[eid] = entry

        reply_score = total_score / len(reply_needed) if reply_needed else 0.0

        # Blend: 40% classification + 60% reply quality
        final = cls_sub['score'] * 0.40 + reply_score * 0.60

        return {
            'score': round(min(1.0, max(0.0, final)), 4),
            'classification_sub_score': cls_sub['score'],
            'reply_sub_score': round(reply_score, 4),
            'replies_needed': len(reply_needed),
            'replies_drafted': sum(1 for e in breakdown.values() if e['drafted']),
            'replies_sent': sum(1 for e in breakdown.values() if e['sent']),
            'breakdown': breakdown,
        }


class WorkflowGrader:
    """Task 3 — Full Inbox Management (Hard).

    5-component weighted composite:
        30% classification + 30% reply + 15% archive + 15% followup + 10% injection

    Plus episode-level bonuses:
        +0.05 inbox completion (≥95% processed)
        +0.02 zero wrong deletions
        +0.03 time efficiency (<70% of step budget used)

    Minus penalties:
        -0.02 per redundant action (capped at 0.10)
        -0.02 per missed deadline (capped at 0.10)
        -0.05 per wrong deletion
    """

    def grade(self, ep: EpisodeState) -> dict:
        gt = ep.ground_truth

        # Sub-graders
        cls = ClassifyGrader().grade(ep)
        reply = ReplyGrader().grade(ep)
        archive = self._grade_archives(ep, gt)
        followup = self._grade_followups(ep, gt)
        injection = self._grade_injections(ep)

        weights = {
            'classify': 0.30, 'reply': 0.30,
            'archive': 0.15, 'followup': 0.15,
            'injection': 0.10,
        }

        weighted_score = (
            cls['score'] * weights['classify'] +
            reply['score'] * weights['reply'] +
            archive['score'] * weights['archive'] +
            followup['score'] * weights['followup'] +
            injection['score'] * weights['injection']
        )

        # Episode-level bonuses
        bonuses = self._episode_bonuses(ep)
        weighted_score += bonuses['total_bonus']

        # Penalties
        penalties = self._compute_penalties(ep, gt)
        weighted_score -= penalties['total_penalty']

        return {
            'score': round(min(1.0, max(0.0, weighted_score)), 4),
            'sub_scores': {
                'classification': cls['score'],
                'reply': reply['score'],
                'archive': archive['score'],
                'followup': followup['score'],
                'injection': injection['score'],
            },
            'episode_bonuses': bonuses,
            'penalties': penalties,
            'weights': weights,
        }

    def _grade_archives(self, ep: EpisodeState, gt: dict) -> dict:
        """Score archiving decisions against ground truth."""
        should = {eid for eid, g in gt.items() if g.get('should_archive')}
        if not should:
            return {'score': 1.0, 'expected': 0, 'correct': 0, 'false': 0}
        correct = len(set(ep.archives) & should)
        false_arch = len(set(ep.archives) - should)
        score = max(0.0, (correct - false_arch * 0.5) / len(should))
        return {
            'score': round(score, 4),
            'expected': len(should), 'correct': correct, 'false': false_arch,
        }

    def _grade_followups(self, ep: EpisodeState, gt: dict) -> dict:
        """Score follow-up scheduling decisions."""
        needed = {eid for eid, g in gt.items() if g.get('needs_followup')}
        if not needed:
            return {'score': 1.0, 'expected': 0, 'scheduled': 0}
        correct = 0
        for eid in ep.followups:
            if eid in needed:
                fu = ep.followups[eid]
                gt_range = gt.get(eid, {}).get('followup_days_range', (1, 7))
                days = fu.get('days', 0)
                if gt_range[0] <= days <= gt_range[1]:
                    correct += 1
                else:
                    correct += 0.5  # Partial credit for scheduling even if days off
        return {
            'score': round(correct / len(needed), 4),
            'expected': len(needed), 'scheduled': len([e for e in ep.followups if e in needed]),
        }

    def _grade_injections(self, ep: EpisodeState) -> dict:
        """Score handling of dynamically injected urgent emails."""
        if not ep.injected_emails:
            return {'score': 1.0, 'injected': 0, 'handled': 0}
        handled = ep.injection_handled & ep.injected_emails
        return {
            'score': round(len(handled) / len(ep.injected_emails), 4),
            'injected': len(ep.injected_emails), 'handled': len(handled),
        }

    def _compute_penalties(self, ep: EpisodeState, gt: dict) -> dict:
        """Compute all penalty deductions."""
        redundant = min(0.10, ep.redundant_actions * 0.02)
        missed = sum(1 for eid, g in gt.items()
                     if g.get('deadline_hint') and eid not in ep.processed_emails)
        deadline_pen = min(0.10, missed * 0.02)
        wrong_del = [d for d in ep.deletions
                     if gt.get(d, {}).get('category') not in ('spam', 'newsletter')]
        delete_pen = min(0.15, len(wrong_del) * 0.05)

        total = redundant + deadline_pen + delete_pen
        return {
            'redundant_steps': round(redundant, 4),
            'missed_deadlines': round(deadline_pen, 4),
            'wrong_deletes': round(delete_pen, 4),
            'total_penalty': round(total, 4),
        }

    def _episode_bonuses(self, ep: EpisodeState) -> dict:
        """Episode-level bonuses for exceptional performance."""
        bonuses = {}

        # Inbox completion bonus: +0.05 if ≥95% processed
        completion = len(ep.processed_emails) / len(ep.inbox) if ep.inbox else 0
        bonuses['completion'] = 0.05 if completion >= 0.95 else 0.0

        # Zero wrong deletions: +0.02
        gt = ep.ground_truth
        wrong_del = [d for d in ep.deletions if gt.get(d, {}).get('category') not in ('spam', 'newsletter')]
        bonuses['zero_wrong_deletes'] = 0.02 if not wrong_del else 0.0

        # Time efficiency: +0.03 if completed in < 70% of max steps
        if ep.step < ep.max_steps * 0.7 and completion >= 0.90:
            bonuses['time_efficiency'] = 0.03
        else:
            bonuses['time_efficiency'] = 0.0

        bonuses['total_bonus'] = round(sum(v for k, v in bonuses.items() if k != 'total_bonus'), 4)
        return bonuses


# ── Grader Registry ──────────────────────────────────────────────────
GRADERS = {
    'classify_inbox': ClassifyGrader,
    'draft_replies': ReplyGrader,
    'manage_inbox': WorkflowGrader,
}
