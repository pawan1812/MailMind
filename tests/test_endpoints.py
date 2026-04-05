import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_tasks_endpoint():
    response = client.get("/tasks")
    assert response.status_code == 200
    tasks = response.json().get("tasks", [])
    assert len(tasks) == 3

def test_reset_and_step():
    response = client.post("/reset?task_id=task1_classify")
    assert response.status_code == 200
    obs = response.json()
    assert "current_email" in obs
    assert obs["step_number"] == 1
    
    session_id = response.headers.get("x-session-id")
    assert session_id is not None
    
    # Step requires action
    action_payload = {
        "email_id": obs["current_email"]["email_id"],
        "classify": {
            "priority": "normal",
            "category": "internal",
            "tags": []
        }
    }
    
    step_resp = client.post(f"/step?session_id={session_id}", json=action_payload)
    assert step_resp.status_code == 200
    step_data = step_resp.json()
    
    assert "reward" in step_data
    assert "done" in step_data
