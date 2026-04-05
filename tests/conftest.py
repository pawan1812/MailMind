"""Shared pytest fixtures for MailMind tests."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """Reusable test client."""
    return TestClient(app)


@pytest.fixture
def easy_episode(client):
    """Reset to easy task and return observation."""
    r = client.post("/reset", json={"task_id": "classify_inbox", "seed": 42})
    return r.json()


@pytest.fixture
def hard_episode(client):
    """Reset to hard task and return observation."""
    r = client.post("/reset", json={"task_id": "manage_inbox", "seed": 42})
    return r.json()
