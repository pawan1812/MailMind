# 📧 MailMind OpenEnv

> **Email Triage & Response AI Agent — OpenEnv Reinforcement Learning Environment**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-orange.svg)](https://openenv.dev)

MailMind is a production-grade OpenEnv RL environment that simulates enterprise email management. An AI agent navigates a synthetically generated inbox — classifying priorities, drafting replies, archiving threads, scheduling follow-ups, and handling urgent injection emails — all through the standard `reset()` / `step()` / `state()` REST API.

---

## 🚀 Quick Start

### Method 1: Direct Launch (Recommended)
```bash
# 1. Double-click run.bat
#    OR run manually:
python -m venv venv
venv\Scripts\activate     # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

### Method 2: Docker
```bash
docker build -t mailmind .
docker run -p 7860:7860 mailmind
```

### Method 3: Docker Compose
```bash
docker-compose up
```

**Open in browser:** [http://localhost:7860/docs](http://localhost:7860/docs) — interactive Swagger UI

---

## 📋 Tasks

| Task | Difficulty | Emails | Steps | What the Agent Does |
|------|-----------|--------|-------|-------------------|
| `classify_inbox` | 🟢 Easy | 15 | 20 | Classify every email by priority + category |
| `draft_replies` | 🟡 Medium | 25 | 30 | Classify + draft contextual replies with correct tone |
| `manage_inbox` | 🔴 Hard | 40+5 | 60 | Full lifecycle: classify, reply, archive, flag, schedule, handle 5 urgent injections |

---

## 🎯 Action Space (8 Actions)

| Action | Fields | Reward |
|--------|--------|--------|
| `classify_email` | priority, category | +0.20 (correct) / -0.10 (wrong) |
| `draft_reply` | email_id, reply_body, tone | +0.06 to +0.40 (semantic similarity) |
| `send_reply` | email_id | +0.15 (on-time) / +0.05 (late) |
| `archive` | — | +0.10 (correct) / -0.15 (wrong) |
| `delete` | — | 0.00 (spam) / **-0.30** (important!) |
| `flag` | flag_reason | +0.10 (VIP/legal) |
| `schedule_followup` | followup_days, followup_note | +0.15 (correct range) |
| `skip` | — | -0.01 |

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reset` | Start a new episode `{"task_id": "classify_inbox", "seed": 42}` |
| `POST` | `/step` | Submit action `{"action": {"action_type": "classify_email", ...}}` |
| `GET` | `/state` | Get current episode state |
| `GET` | `/tasks` | List all tasks with metadata |
| `POST` | `/grader` | Grade completed episode → 0.0–1.0 score |
| `POST` | `/baseline` | Get baseline reference scores |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |

---

## 🤖 Running the Baseline Agent

The baseline script uses OpenAI GPT-4o-mini to play all 3 tasks:

```bash
# Set your API key
set OPENAI_API_KEY=sk-...

# Make sure the server is running first, then:
python -m baseline.run_baseline
```

**Expected baseline scores (GPT-4o-mini, temp=0.2):**
| Task | Score Range |
|------|-----------|
| classify_inbox | 0.72 – 0.82 |
| draft_replies | 0.52 – 0.65 |
| manage_inbox | 0.31 – 0.46 |

---

## 🏗️ Project Structure

```
mailmind/
├── app/
│   ├── main.py               ← FastAPI application factory
│   ├── config.py              ← Settings (env vars)
│   ├── dependencies.py        ← Session pool
│   ├── core/                  ← Domain logic
│   │   ├── environment.py     ← MailMindEnv (reset/step/state/grade)
│   │   ├── episode.py         ← EpisodeState dataclass
│   │   ├── inbox.py           ← InboxSimulator (Faker-based)
│   │   ├── rewards.py         ← RewardCalculator (12 components)
│   │   └── injection.py       ← Dynamic email injection (hard task)
│   ├── models/                ← Pydantic v2 schemas
│   │   ├── observation.py     ← Email, InboxSummary, Observation
│   │   ├── action.py          ← Action (8 types)
│   │   └── reward.py          ← Reward, RewardBreakdown, GraderResult
│   ├── routes/                ← FastAPI route handlers
│   │   ├── env_routes.py      ← /reset, /step, /state
│   │   ├── task_routes.py     ← /tasks
│   │   ├── grader_routes.py   ← /grader
│   │   ├── baseline_routes.py ← /baseline
│   │   └── health_routes.py   ← /health
│   └── db/                    ← Firebase persistence (optional)
│       └── firebase_client.py ← Auto-fallback to in-memory
├── baseline/
│   ├── run_baseline.py        ← OpenAI-powered baseline agent
│   └── prompts.py             ← System prompt + user turn builder
├── data/
│   ├── fixtures/              ← Task fixture JSONs
│   └── personas/              ← Sender role definitions
├── openenv.yaml               ← OpenEnv spec file
├── Dockerfile                 ← Multi-stage Docker build
├── docker-compose.yml         ← Local dev config
├── requirements.txt           ← Python dependencies
├── run.bat                    ← One-click Windows launcher
└── README.md                  ← This file
```

---

## 🔥 Firebase Setup (Optional)

Firebase Firestore provides persistent episode storage. **The server runs perfectly without it** (using in-memory storage).

To enable Firebase:
1. Create a project at [console.firebase.google.com](https://console.firebase.google.com)
2. Generate a service account key (JSON)
3. Set the environment variable:
   ```bash
   set GOOGLE_APPLICATION_CREDENTIALS=./firebase-service-account.json
   set FIREBASE_PROJECT_ID=your-project-id
   ```

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

## 📊 Reward System

Every step returns a **dense, interpretable** reward with 12 named sub-components:

| Component | Range | Description |
|-----------|-------|-------------|
| classification_accuracy | ±0.20 | Priority + category match |
| reply_relevance | -0.10 to +0.40 | Semantic similarity to reference |
| tone_match | +0.10 | Correct tone selection |
| timeliness_bonus | +0.05 to +0.15 | Before/after deadline |
| archive_correctness | ±0.15 | Correct archive decisions |
| flag_correctness | +0.10 | VIP/legal flagging |
| followup_quality | ±0.15 | Follow-up scheduling accuracy |
| injection_response | +0.20 | Handling urgent injections |
| wrong_delete_penalty | -0.30 | Deleting important emails |
| redundant_action_penalty | -0.05 | Repeating processed emails |
| missed_deadline_penalty | -0.20 | Missing deadline emails |
| step_waste_penalty | -0.01 | Skipping without action |

---

## 📜 License

Apache-2.0 — see [LICENSE](LICENSE)

---

**MailMind** — *Inbox intelligence. Benchmarked.* 📧
