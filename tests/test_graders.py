"""Tests for the modular grader system."""

import pytest
from app.core.graders import ClassifyGrader, ReplyGrader, WorkflowGrader
from app.core.episode import EpisodeState
from app.core.inbox import InboxSimulator


class TestClassifyGrader:
    def test_perfect_score(self):
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("classify_inbox")
        ep = EpisodeState(task_id="classify_inbox", inbox=inbox, ground_truth=gt)

        # Classify all emails correctly
        for eid, truth in gt.items():
            ep.classifications[eid] = {
                'priority': truth['priority'],
                'category': truth['category'],
            }

        grader = ClassifyGrader()
        result = grader.grade(ep)
        assert result['score'] == 1.0

    def test_zero_score_no_classifications(self):
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("classify_inbox")
        ep = EpisodeState(task_id="classify_inbox", inbox=inbox, ground_truth=gt)

        grader = ClassifyGrader()
        result = grader.grade(ep)
        assert result['score'] == 0.0

    def test_partial_score(self):
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("classify_inbox")
        ep = EpisodeState(task_id="classify_inbox", inbox=inbox, ground_truth=gt)

        # Classify only priority correctly for all
        for eid, truth in gt.items():
            ep.classifications[eid] = {
                'priority': truth['priority'],
                'category': 'other',  # wrong
            }

        grader = ClassifyGrader()
        result = grader.grade(ep)
        assert 0.5 < result['score'] < 0.7  # Should get 0.6 (only priority correct)

    def test_breakdown_present(self):
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("classify_inbox")
        ep = EpisodeState(task_id="classify_inbox", inbox=inbox, ground_truth=gt)

        grader = ClassifyGrader()
        result = grader.grade(ep)
        assert 'breakdown' in result
        assert len(result['breakdown']) == len(gt)


class TestReplyGrader:
    def test_no_replies_needed(self):
        ep = EpisodeState(task_id="draft_replies", ground_truth={
            'em_001': {'requires_reply': False},
        })
        grader = ReplyGrader()
        result = grader.grade(ep)
        assert result['score'] == 1.0

    def test_sent_reply_scores_higher(self):
        gt = {
            'em_001': {'requires_reply': True, 'expected_tone': 'formal'},
        }
        ep = EpisodeState(task_id="draft_replies", ground_truth=gt)
        ep.drafts['em_001'] = {'body': 'test', 'tone': 'formal', 'sent': True}

        grader = ReplyGrader()
        result = grader.grade(ep)
        assert result['score'] == 1.0  # sent + correct tone


class TestWorkflowGrader:
    def test_episode_bonuses(self):
        grader = WorkflowGrader()
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("manage_inbox")
        ep = EpisodeState(
            task_id="manage_inbox",
            inbox=inbox,
            ground_truth=gt,
            max_steps=60,
        )

        bonuses = grader._episode_bonuses(ep)
        assert 'completion' in bonuses
        assert 'zero_wrong_deletes' in bonuses
        assert 'time_efficiency' in bonuses
        assert 'total_bonus' in bonuses
