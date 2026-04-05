import pytest
from app.rewards.reward_engine import calculate_reward
from app.models.state import EnvState
from app.models.observation import Email
from app.models.action import Action, ClassifyAction
from datetime import datetime

def test_calculate_reward():
    email = Email(
        email_id="123",
        subject="Test",
        sender="test@test.com",
        sender_name="Test",
        sender_role="Unknown",
        body="Test",
        timestamp=datetime.now(),
        is_urgent=True
    )
    
    state = EnvState(
        task_id="task1_classify",
        inbox=[email],
        max_steps=1,
        ground_truth={"123": {"priority": "urgent", "category": "internal", "expected_tone": "professional", "reference_reply": "none"}}
    )
    
    action = Action(
        email_id="123",
        classify=ClassifyAction(
            priority="urgent",
            category="internal",
            tags=[]
        ),
        reply=None,
        archive=None,
        delete=None,
        schedule=None,
        skip=None
    )
    
    reward = calculate_reward(state, action)
    assert reward.classification_score > 0
    assert reward.total > 0
    assert reward.penalties == 0
