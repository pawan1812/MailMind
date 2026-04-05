# 📧 MailMind — OpenEnv Environment

> **Email Triage & Response AI Agent — OpenEnv Reinforcement Learning Environment**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-orange.svg)](https://openenv.dev)

---

## 🎯 What Is MailMind?

MailMind is a production-grade **OpenEnv reinforcement learning environment** that simulates real-world enterprise email management. An AI agent navigates a synthetically generated inbox — classifying priorities, drafting replies, archiving threads, scheduling follow-ups, and handling urgent injection emails — all through the standard `reset()` / `step()` / `state()` REST API.

**Why Email?** Every knowledge worker spends 2–4 hours/day on email. A well-trained agent on MailMind translates directly to a deployable product. The domain is universally understood, graders are deterministic, and difficulty scales naturally from classification (easy) to full workflow management (hard).

---

## 📋 Tasks (3 Difficulty Levels)

| Task ID | Name | Difficulty | Emails | Max Steps | Objective |
|---------|------|-----------|--------|-----------|-----------|
| `classify_inbox` | Email Classification | 🟢 Easy | 15 | 20 | Classify every email by priority + category |
| `draft_replies` | Reply Drafting | 🟡 Medium | 25 | 30 | Classify + draft contextual replies with correct tone |
| `manage_inbox` | Full Inbox Management | 🔴 Hard | 40+5 | 60 | Full lifecycle: classify, reply, archive, flag, schedule, handle 5 urgent dynamic injections |

Each task returns a deterministic grader score in **[0.0, 1.0]** range.

---

## 🎮 Action Space (8 Actions)

```json
{
  "action_type": "classify_email | draft_reply | send_reply | archive | delete | flag | schedule_followup | skip",
  "priority": "urgent | high | medium | low",
  "category": "meeting_request | action_required | fyi | newsletter | spam | invoice | hr | legal | personal | complaint | approval_needed | other",
  "email_id": "<uuid>",
  "reply_body": "<reply text, max 2000 chars>",
  "tone": "formal | professional | friendly | brief | assertive",
  "followup_days": 1-30,
  "followup_note": "<note, max 200 chars>",
  "flag_reason": "vip | legal | urgent | awaiting_reply | needs_review",
  "tags": ["meeting", "deadline", "invoice"]
}
```

Only include fields relevant to your chosen `action_type`.

---

## 👁️ Observation Space

Each `step()` and `reset()` returns:

```json
{
  "episode_id": "uuid",
  "step": 3,
  "current_email": {
    "email_id": "uuid",
    "subject": "Q3 Budget Review Meeting",
    "sender": "CEO",
    "sender_importance": "ceo",
    "body": "Hi, can we schedule...",
    "received_at": "2024-01-15T10:30:00",
    "has_attachment": false,
    "thread": { "messages": [...] },
    "deadline_hint": "by EOD Friday"
  },
  "inbox_summary": {
    "total_emails": 15,
    "unread_count": 12,
    "processed_count": 3,
    "step_budget_remaining": 17
  },
  "recent_actions": ["Step 1: classify_email → +0.20"],
  "episode_score": 0.30,
  "done": false
}
```

---

## 📊 Reward System (Dense, 12-Component)

Every step returns a **dense, interpretable** reward capped at **±0.5 per step**:

| Component | Range | Trigger |
|-----------|-------|---------|
| classification_accuracy | ±0.20 | Priority + category match vs ground truth |
| reply_relevance | -0.10 to +0.40 | Semantic similarity to reference reply |
| tone_match | +0.10 | Correct tone for sender role |
| timeliness_bonus | +0.05 to +0.15 | Replied before deadline |
| archive_correctness | ±0.15 | Archive decision matches ground truth |
| flag_correctness | +0.10 | Correct VIP/legal flag |
| followup_quality | ±0.15 | Follow-up days within expected window |
| injection_response | +0.20 | Handling urgent mid-episode injections |
| wrong_delete_penalty | -0.30 | Deleting important emails |
| redundant_action_penalty | -0.05 | Repeating processed emails |
| step_waste_penalty | -0.01 | Skipping without reason |

**Episode-level bonuses:** +0.05 inbox completion, +0.02 zero wrong deletes, +0.03 time efficiency.

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reset` | Start a new episode `{"task_id": "classify_inbox", "seed": 42}` |
| `POST` | `/step` | Submit action `{"action": {"action_type": "classify_email", ...}}` |
| `GET` | `/state` | Get current episode state |
| `GET` | `/tasks` | List all 3 tasks with metadata |
| `POST` | `/grader` | Grade completed episode → 0.0–1.0 |
| `POST` | `/baseline` | Get baseline reference scores |
| `GET` | `/health` | Health check + version |
| `GET` | `/openenv.yaml` | Serve OpenEnv spec |

---

## 🚀 Setup & Launch

### Option 1: Local (Recommended for development)

```bash
git clone https://github.com/pawan1812/MailMind.git
cd MailMind
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate      # Linux/Mac
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 7860
```

Open **http://localhost:7860/docs** for the interactive Swagger UI.

### Option 2: Docker

```bash
docker build -t mailmind .
docker run -p 7860:7860 mailmind
```

### Option 3: Docker Compose

```bash
docker-compose up
```

---

## 🤖 Running the Inference Script

The inference script (`inference.py`) runs all 3 tasks and outputs structured logs:

```bash
# Set environment variables
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="hf_your_token_here"

# Make sure the server is running, then:
python inference.py
```

**Output format:**
```
[START] task=classify_inbox env=mailmind model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=classify_email reward=0.20 done=false error=null
[STEP] step=2 action=classify_email reward=0.20 done=false error=null
...
[END] success=true steps=15 score=0.78 rewards=0.20,0.20,...
[START] task=draft_replies env=mailmind model=Qwen/Qwen2.5-72B-Instruct
...
[END] success=true steps=25 score=0.58 rewards=...
[START] task=manage_inbox env=mailmind model=Qwen/Qwen2.5-72B-Instruct
...
[END] success=true steps=40 score=0.38 rewards=...
```

### Baseline Scores (GPT-4o-mini, temp=0.2)

| Task | Score Range |
|------|-----------|
| classify_inbox | 0.72 – 0.82 |
| draft_replies | 0.52 – 0.65 |
| manage_inbox | 0.31 – 0.46 |
| **Average** | **~0.58** |

---

## 🧪 Testing

```bash
python -m pytest tests/ -v
# 64+ tests passed in ~2.7s
```

---

## 🏗️ Project Structure

```
mailmind/
├── app/
│   ├── main.py               # FastAPI app with lifespan handler
│   ├── config.py              # Pydantic V2 settings
│   ├── dependencies.py        # Session pool
│   ├── logging_config.py      # Structlog + Rich logging
│   ├── core/                  # Domain logic
│   │   ├── environment.py     # MailMindEnv (reset/step/state/grade)
│   │   ├── episode.py         # EpisodeState dataclass
│   │   ├── inbox.py           # InboxSimulator (Faker-based)
│   │   ├── graders.py         # Modular graders (easy/med/hard)
│   │   ├── rewards.py         # RewardCalculator (12 components)
│   │   └── injection.py       # Dynamic email injection (hard task)
│   ├── models/                # Pydantic v2 schemas
│   │   ├── observation.py     # Email, InboxSummary, Observation
│   │   ├── action.py          # Action (8 types + tags)
│   │   └── reward.py          # Reward, RewardBreakdown, GraderResult
│   ├── routes/                # FastAPI endpoints
│   └── db/                    # Firebase + in-memory fallback
├── data/
│   ├── email_templates/       # Jinja2-style body templates
│   ├── fixtures/              # Task ground truth JSONs
│   └── personas/              # Sender role definitions
├── tests/
│   ├── conftest.py            # Shared fixtures
│   ├── test_mailmind.py       # 57 endpoint + integration tests
│   └── test_graders.py        # 7 modular grader tests
├── inference.py               # Hackathon inference script (ALL 3 tasks)
├── openenv.yaml               # OpenEnv spec file
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml
├── requirements.txt
├── LICENSE                    # Apache-2.0
└── README.md
```

---

## 📜 License

Apache-2.0 — see [LICENSE](LICENSE)

---

**MailMind** — *Inbox intelligence. Benchmarked.* 📧
