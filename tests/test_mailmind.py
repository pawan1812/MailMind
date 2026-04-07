"""Pytest test suite for MailMind v1.0.0 — unit + integration tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════
#  Health / Tasks / Baseline (stateless endpoints)
# ═══════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    def test_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_version(self):
        data = client.get("/health").json()
        assert data["version"] == "1.0.0"

    def test_status_healthy(self):
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_firebase_field_present(self):
        data = client.get("/health").json()
        assert "firebase" in data


class TestTasksEndpoint:
    def test_returns_200(self):
        assert client.get("/tasks").status_code == 200

    def test_three_tasks(self):
        tasks = client.get("/tasks").json()
        assert len(tasks) == 3

    def test_task_ids(self):
        ids = [t["id"] for t in client.get("/tasks").json()]
        assert "classify_inbox" in ids
        assert "draft_replies" in ids
        assert "manage_inbox" in ids

    def test_task_metadata_complete(self):
        for t in client.get("/tasks").json():
            assert "max_steps" in t
            assert "description" in t
            assert "action_types" in t
            assert "difficulty" in t


class TestBaselineEndpoint:
    def test_returns_200(self):
        assert client.post("/baseline").status_code == 200

    def test_has_scores(self):
        data = client.post("/baseline").json()
        assert "scores" in data
        assert len(data["scores"]) == 3

    def test_has_model(self):
        assert "model" in client.post("/baseline").json()


class TestOpenenvYaml:
    def test_returns_200(self):
        assert client.get("/openenv.yaml").status_code == 200

    def test_contains_mailmind(self):
        assert "mailmind" in client.get("/openenv.yaml").text.lower()

    def test_contains_version(self):
        assert "1.0.0" in client.get("/openenv.yaml").text


# ═══════════════════════════════════════════════════════════════════
#  Reset Endpoint
# ═══════════════════════════════════════════════════════════════════

class TestResetEndpoint:
    def test_easy_task(self):
        r = client.post("/reset", json={"task_id": "classify_inbox", "seed": 42})
        assert r.status_code == 200
        obs = r.json()
        assert obs["inbox_summary"]["total_emails"] == 15
        assert obs["inbox_summary"]["step_budget_remaining"] == 20
        assert obs["step"] == 0
        assert obs["done"] is False

    def test_medium_task(self):
        r = client.post("/reset", json={"task_id": "draft_replies", "seed": 42})
        obs = r.json()
        assert obs["inbox_summary"]["total_emails"] == 25
        assert obs["inbox_summary"]["step_budget_remaining"] == 30

    def test_hard_task(self):
        r = client.post("/reset", json={"task_id": "manage_inbox", "seed": 42})
        obs = r.json()
        assert obs["inbox_summary"]["total_emails"] == 40
        assert obs["inbox_summary"]["step_budget_remaining"] == 60

    def test_invalid_task(self):
        r = client.post("/reset", json={"task_id": "fake_task"})
        assert r.status_code == 422

    def test_episode_id_assigned(self):
        obs = client.post("/reset", json={"task_id": "classify_inbox", "seed": 42}).json()
        assert obs["episode_id"].startswith("ep_")

    def test_current_email_present(self):
        obs = client.post("/reset", json={"task_id": "classify_inbox", "seed": 42}).json()
        em = obs["current_email"]
        assert "email_id" in em
        assert "subject" in em
        assert "sender" in em
        assert "sender_email" in em
        assert "sender_domain" in em
        assert "sender_importance" in em
        assert "body" in em
        assert len(em["body"]) > 10

    def test_inbox_summary_fields(self):
        obs = client.post("/reset", json={"task_id": "classify_inbox", "seed": 42}).json()
        s = obs["inbox_summary"]
        assert "total_emails" in s
        assert "unread_count" in s
        assert "processed_count" in s
        assert "step_budget_remaining" in s
        assert "categories" in s
        assert isinstance(s["categories"], dict)

    def test_deterministic_seeding(self):
        obs1 = client.post("/reset", json={"task_id": "classify_inbox", "seed": 99}).json()
        obs2 = client.post("/reset", json={"task_id": "classify_inbox", "seed": 99}).json()
        assert obs1["current_email"]["subject"] == obs2["current_email"]["subject"]

    def test_different_seeds_different_emails(self):
        obs1 = client.post("/reset", json={"task_id": "classify_inbox", "seed": 1}).json()
        obs2 = client.post("/reset", json={"task_id": "classify_inbox", "seed": 999}).json()
        assert obs1["current_email"]["subject"] != obs2["current_email"]["subject"]


# ═══════════════════════════════════════════════════════════════════
#  Step Endpoint — All 8 Action Types
# ═══════════════════════════════════════════════════════════════════

class TestStepActions:
    """Tests each of the 8 action types."""

    @pytest.fixture(autouse=True)
    def reset_episode(self):
        """Reset to easy task before each test."""
        client.post("/reset", json={"task_id": "classify_inbox", "seed": 42})

    def test_classify_email(self):
        r = client.post("/step", json={
            "action": {"action_type": "classify_email", "priority": "medium", "category": "personal"}
        })
        assert r.status_code == 200
        data = r.json()
        assert "reward" in data
        assert "observation" in data
        assert "done" in data
        assert data["done"] is False

    def test_archive(self):
        # First classify, then archive
        client.post("/step", json={
            "action": {"action_type": "classify_email", "priority": "low", "category": "fyi"}
        })
        r = client.post("/step", json={"action": {"action_type": "archive"}})
        assert r.status_code == 200

    def test_skip(self):
        r = client.post("/step", json={"action": {"action_type": "skip"}})
        assert r.status_code == 200
        bd = r.json()["reward"]["breakdown"]
        assert bd["step_waste_penalty"] == -0.01

    def test_flag(self):
        r = client.post("/step", json={
            "action": {"action_type": "flag", "flag_reason": "vip"}
        })
        assert r.status_code == 200

    def test_draft_reply(self):
        r = client.post("/step", json={
            "action": {
                "action_type": "draft_reply",
                "email_id": "em_000",
                "reply_body": "Thank you for your email. I will review shortly.",
                "tone": "formal"
            }
        })
        assert r.status_code == 200
        bd = r.json()["reward"]["breakdown"]
        assert "reply_relevance" in bd
        assert "tone_match" in bd

    def test_send_reply(self):
        # First draft
        client.post("/step", json={
            "action": {
                "action_type": "draft_reply",
                "email_id": "em_000",
                "reply_body": "Thank you.",
                "tone": "formal"
            }
        })
        # Then send
        r = client.post("/step", json={
            "action": {"action_type": "send_reply", "email_id": "em_000"}
        })
        assert r.status_code == 200

    def test_schedule_followup(self):
        r = client.post("/step", json={
            "action": {
                "action_type": "schedule_followup",
                "email_id": "em_000",
                "followup_days": 3,
                "followup_note": "Check back Wednesday"
            }
        })
        assert r.status_code == 200

    def test_delete(self):
        r = client.post("/step", json={"action": {"action_type": "delete"}})
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════
#  Reward Structure
# ═══════════════════════════════════════════════════════════════════

class TestRewardStructure:
    @pytest.fixture(autouse=True)
    def reset_and_step(self):
        client.post("/reset", json={"task_id": "classify_inbox", "seed": 42})
        self.result = client.post("/step", json={
            "action": {"action_type": "classify_email", "priority": "medium", "category": "fyi"}
        }).json()

    def test_reward_has_value(self):
        assert isinstance(self.result["reward"]["value"], (int, float))

    def test_reward_has_cumulative(self):
        assert isinstance(self.result["reward"]["cumulative"], (int, float))

    def test_reward_capped(self):
        assert -0.5 <= self.result["reward"]["value"] <= 0.5

    def test_reward_has_reason(self):
        assert len(self.result["reward"]["reason"]) > 0

    def test_reward_has_step(self):
        assert "step" in self.result["reward"]

    def test_breakdown_has_12_components(self):
        bd = self.result["reward"]["breakdown"]
        expected = [
            "classification_accuracy", "reply_relevance", "tone_match",
            "timeliness_bonus", "archive_correctness", "flag_correctness",
            "followup_quality", "injection_response", "wrong_delete_penalty",
            "redundant_action_penalty", "missed_deadline_penalty", "step_waste_penalty"
        ]
        for k in expected:
            assert k in bd, f"Missing breakdown key: {k}"


# ═══════════════════════════════════════════════════════════════════
#  Validation Errors
# ═══════════════════════════════════════════════════════════════════

class TestValidationErrors:
    @pytest.fixture(autouse=True)
    def reset_episode(self):
        client.post("/reset", json={"task_id": "classify_inbox", "seed": 42})

    def test_classify_missing_priority(self):
        r = client.post("/step", json={
            "action": {"action_type": "classify_email"}
        })
        assert r.status_code == 422

    def test_draft_reply_missing_email_id(self):
        r = client.post("/step", json={
            "action": {"action_type": "draft_reply"}
        })
        assert r.status_code == 422

    def test_invalid_action_type(self):
        r = client.post("/step", json={
            "action": {"action_type": "invalid_type"}
        })
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════
#  State Endpoint
# ═══════════════════════════════════════════════════════════════════

class TestStateEndpoint:
    def test_no_episode(self):
        # fresh session
        r = client.get("/state", headers={"X-Session-ID": "test_no_episode_xxx"})
        assert r.status_code == 200
        assert r.json()["status"] == "no_active_episode"

    def test_active_episode(self):
        client.post("/reset", json={"task_id": "classify_inbox", "seed": 42})
        client.post("/step", json={
            "action": {"action_type": "classify_email", "priority": "low", "category": "spam"}
        })
        r = client.get("/state")
        data = r.json()
        assert data["task_id"] == "classify_inbox"
        assert data["step"] >= 1
        assert "cumulative_reward" in data
        assert "processed_count" in data


# ═══════════════════════════════════════════════════════════════════
#  Grader Endpoint
# ═══════════════════════════════════════════════════════════════════

class TestGraderEndpoint:
    def test_grader_after_actions(self):
        client.post("/reset", json={"task_id": "classify_inbox", "seed": 42})
        # Take a few actions
        for _ in range(3):
            client.post("/step", json={
                "action": {"action_type": "classify_email", "priority": "medium", "category": "fyi"}
            })
        r = client.post("/grader")
        assert r.status_code == 200
        grade = r.json()
        assert 0.0 <= grade["final_score"] <= 1.0
        assert "component_scores" in grade
        assert "classification" in grade["component_scores"]
        assert "reply" in grade["component_scores"]
        assert "archive" in grade["component_scores"]
        assert "followup" in grade["component_scores"]
        assert "injection" in grade["component_scores"]
        assert "weighted_scores" in grade
        assert "penalties" in grade
        assert "efficiency_ratio" in grade
        assert "total_steps_used" in grade
        assert "step_budget" in grade


# ═══════════════════════════════════════════════════════════════════
#  Session Isolation
# ═══════════════════════════════════════════════════════════════════

class TestSessionIsolation:
    def test_different_sessions(self):
        r_a = client.post("/reset",
                          json={"task_id": "classify_inbox", "seed": 42},
                          headers={"X-Session-ID": "iso_A"})
        r_b = client.post("/reset",
                          json={"task_id": "draft_replies", "seed": 42},
                          headers={"X-Session-ID": "iso_B"})
        assert r_a.json()["episode_id"] != r_b.json()["episode_id"]

        st_a = client.get("/state", headers={"X-Session-ID": "iso_A"}).json()
        st_b = client.get("/state", headers={"X-Session-ID": "iso_B"}).json()
        assert st_a["task_id"] == "classify_inbox"
        assert st_b["task_id"] == "draft_replies"


# ═══════════════════════════════════════════════════════════════════
#  Core Unit Tests (non-HTTP)
# ═══════════════════════════════════════════════════════════════════

class TestInboxSimulator:
    def test_easy_generates_15(self):
        from app.core.inbox import InboxSimulator
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("classify_inbox")
        assert len(inbox) == 15
        assert len(gt) == 15

    def test_medium_generates_25(self):
        from app.core.inbox import InboxSimulator
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("draft_replies")
        assert len(inbox) == 25

    def test_hard_generates_40(self):
        from app.core.inbox import InboxSimulator
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("manage_inbox")
        assert len(inbox) == 40

    def test_emails_have_required_fields(self):
        from app.core.inbox import InboxSimulator
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("classify_inbox")
        for em in inbox:
            assert em.email_id
            assert em.subject
            assert em.sender
            assert em.sender_email
            assert em.body
            assert em.sender_importance

    def test_ground_truth_has_required_fields(self):
        from app.core.inbox import InboxSimulator
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("classify_inbox")
        for eid, truth in gt.items():
            assert "priority" in truth
            assert "category" in truth
            assert "requires_reply" in truth
            assert "reference_reply" in truth


class TestEpisodeState:
    def test_defaults(self):
        from app.core.episode import EpisodeState
        ep = EpisodeState()
        assert ep.step == 0
        assert ep.done is False
        assert ep.episode_id.startswith("ep_")

    def test_advance(self):
        from app.core.episode import EpisodeState
        ep = EpisodeState()
        assert ep.current_idx == 0
        ep.advance()
        assert ep.current_idx == 1


class TestRewardCalculator:
    def test_skip_penalty(self):
        from app.core.rewards import RewardCalculator
        from app.core.episode import EpisodeState
        from app.models.action import Action
        calc = RewardCalculator()
        ep = EpisodeState()
        action = Action(action_type="skip")
        reward = calc.compute(action, ep)
        assert reward.breakdown.step_waste_penalty == -0.01

    def test_reward_capped(self):
        from app.core.rewards import RewardCalculator
        from app.core.episode import EpisodeState
        from app.models.action import Action
        calc = RewardCalculator()
        ep = EpisodeState()
        action = Action(action_type="archive")
        reward = calc.compute(action, ep)
        assert -0.5 <= reward.value <= 0.5


class TestDynamicInjector:
    def test_only_injects_on_hard_task(self):
        from app.core.injection import DynamicInjector
        from app.core.episode import EpisodeState
        inj = DynamicInjector()
        ep = EpisodeState(task_id="classify_inbox", step=10)
        result = inj.check_and_inject(ep)
        assert result is None  # Not hard task

    def test_injects_at_step_10(self):
        from app.core.injection import DynamicInjector
        from app.core.episode import EpisodeState
        from app.core.inbox import InboxSimulator
        inj = DynamicInjector()
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("manage_inbox")
        ep = EpisodeState(task_id="manage_inbox", step=10, inbox=inbox, ground_truth=gt)
        result = inj.check_and_inject(ep)
        assert result is not None
        assert result.injected is True
        assert result.email_id == "em_inj_001"
        assert "em_inj_001" in ep.injected_emails

    def test_no_double_injection(self):
        from app.core.injection import DynamicInjector
        from app.core.episode import EpisodeState
        from app.core.inbox import InboxSimulator
        inj = DynamicInjector()
        sim = InboxSimulator(seed=42)
        inbox, gt = sim.generate("manage_inbox")
        ep = EpisodeState(task_id="manage_inbox", step=10, inbox=inbox, ground_truth=gt)
        inj.check_and_inject(ep)
        result2 = inj.check_and_inject(ep)
        assert result2 is None  # Already injected


class TestMailMindEnv:
    def test_full_episode_flow(self):
        from app.core.environment import MailMindEnv
        env = MailMindEnv(session_id="test_flow")
        from app.models.action import Action

        # Reset
        obs = env.reset(task_id="classify_inbox", seed=42)
        assert obs.step == 0
        assert obs.current_email is not None

        # Step
        action = Action(action_type="classify_email", priority="medium", category="fyi")
        result = env.step(action)
        assert result.reward.value is not None
        assert result.done is False

        # State
        state = env.state()
        assert state["step"] == 1

        # Grade
        grade = env.grade()
        assert 0.0 <= grade.final_score <= 1.0
