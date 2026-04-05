"""Grader modules — Per-task deterministic grading logic. PRD §6."""

from app.core.episode import EpisodeState

class ClassifyGrader:
    """Task 1 — Email Classification (Easy). PRD §6.1."""

    def grade(self, ep: EpisodeState) -> dict:
        gt = ep.ground_truth
        total = len(gt)
        if total == 0:
            return {'score': 0.0, 'breakdown': {}}

        p_correct = 0
        c_correct = 0
        breakdown = {}

        for eid, truth in gt.items():
            pred = ep.classifications.get(eid)
            ok_p = ok_c = False
            if pred:
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

        # PRD §6.1: Score = (exact priority matches / N) * 0.6 + (exact category matches / N) * 0.4
        score = (p_correct / total) * 0.6 + (c_correct / total) * 0.4

        return {
            'score': round(score, 4),
            'priority_accuracy': round(p_correct / total, 4),
            'category_accuracy': round(c_correct / total, 4),
            'total_emails': total,
            'classified': len(ep.classifications),
            'breakdown': breakdown,
        }


class ReplyGrader:
    """Task 2 — Reply Drafting (Medium). PRD §6.2."""

    def grade(self, ep: EpisodeState) -> dict:
        gt = ep.ground_truth
        reply_needed = {eid: g for eid, g in gt.items() if g.get('requires_reply')}

        if not reply_needed:
            return {'score': 1.0, 'breakdown': {}}

        total_score = 0.0
        breakdown = {}

        for eid, truth in reply_needed.items():
            draft = ep.drafts.get(eid)
            entry = {'drafted': False, 'sent': False, 'tone_correct': False, 'score': 0.0}

            if draft:
                entry['drafted'] = True
                draft_score = 0.3  # Base for having a draft

                if draft.get('sent'):
                    entry['sent'] = True
                    draft_score = 0.7  # Sent reply

                if draft.get('tone') == truth.get('expected_tone'):
                    entry['tone_correct'] = True
                    draft_score += 0.3

                entry['score'] = round(draft_score, 2)
                total_score += draft_score

            breakdown[eid] = entry

        final = total_score / len(reply_needed)
        return {
            'score': round(final, 4),
            'replies_needed': len(reply_needed),
            'replies_drafted': sum(1 for e in breakdown.values() if e['drafted']),
            'replies_sent': sum(1 for e in breakdown.values() if e['sent']),
            'breakdown': breakdown,
        }


class WorkflowGrader:
    """Task 3 — Full Inbox Management (Hard). PRD §6.3."""

    def grade(self, ep: EpisodeState) -> dict:
        gt = ep.ground_truth

        # Sub-graders
        cls = ClassifyGrader().grade(ep)
        reply = ReplyGrader().grade(ep)
        archive = self._grade_archives(ep, gt)
        followup = self._grade_followups(ep, gt)
        injection = self._grade_injections(ep)

        # PRD §6.3 weights: 0.30 classify + 0.35 reply + 0.20 schedule + 0.15 no_delete
        weights = {'classify': 0.30, 'reply': 0.35, 'archive': 0.15, 'followup': 0.10, 'injection': 0.10}

        weighted_score = (
            cls['score'] * weights['classify'] +
            reply['score'] * weights['reply'] +
            archive['score'] * weights['archive'] +
            followup['score'] * weights['followup'] +
            injection['score'] * weights['injection']
        )

        # Episode-level bonuses (PRD §5.2)
        bonuses = self._episode_bonuses(ep)
        weighted_score += bonuses['total_bonus']

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
            'weights': weights,
        }

    def _grade_archives(self, ep: EpisodeState, gt: dict) -> dict:
        should = {eid for eid, g in gt.items() if g.get('should_archive')}
        if not should:
            return {'score': 1.0}
        correct = len(set(ep.archives) & should)
        false_arch = len(set(ep.archives) - should)
        score = max(0.0, (correct - false_arch * 0.5) / len(should))
        return {'score': round(score, 4), 'expected': len(should), 'correct': correct, 'false': false_arch}

    def _grade_followups(self, ep: EpisodeState, gt: dict) -> dict:
        needed = {eid for eid, g in gt.items() if g.get('needs_followup')}
        if not needed:
            return {'score': 1.0}
        correct = sum(1 for eid in ep.followups if eid in needed)
        return {'score': round(correct / len(needed), 4), 'expected': len(needed), 'scheduled': correct}

    def _grade_injections(self, ep: EpisodeState) -> dict:
        if not ep.injected_emails:
            return {'score': 1.0}
        handled = ep.injection_handled & ep.injected_emails
        return {'score': round(len(handled) / len(ep.injected_emails), 4),
                'injected': len(ep.injected_emails), 'handled': len(handled)}

    def _episode_bonuses(self, ep: EpisodeState) -> dict:
        """PRD §5.2 — Episode-level bonuses."""
        bonuses = {}

        # Inbox completion bonus: +0.05 if all emails processed
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

        bonuses['total_bonus'] = sum(bonuses.values())
        return bonuses


# Convenience map
GRADERS = {
    'classify_inbox': ClassifyGrader,
    'draft_replies': ReplyGrader,
    'manage_inbox': WorkflowGrader,
}
