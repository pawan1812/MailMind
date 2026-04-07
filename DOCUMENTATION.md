# MailMind: Extended Documentation & Agent Guide

## 🏆 Project Scores (Baseline Evaluation)
According to the built-in OpenEnv validation baseline runs using `gpt-4o-mini` (temperature `0.2`), here are the scores out of a maximum of **`1.0`**:

* **🟢 Classify Inbox (Easy):** `0.7745`
* **🟡 Draft Replies (Medium):** `0.5820`
* **🔴 Manage Inbox (Hard):** `0.3855`
* **✨ Global Average:** **`0.5806`**

*(Note: The hard task introduces a dynamic penalty for actions such as deleting necessary emails or missing strict deadlines, keeping baseline metrics suppressed for regular models).*

---

## 🛠️ How MailMind Works Inside

MailMind functions as an **OpenEnv-compatible Reinforcement Learning Environment**, heavily intended for evaluating Email Triage models. It uses a clean, reproducible REST API to act similarly to an enterprise email inbox. Here's the sequence of operations:

1. **Initialization (`/reset`)**: A new test iteration spins up, creating an inbox dynamically seeded with assorted realistic corporate and external emails (managed by Jinja templates and Faker rules).
2. **Observation (`/state` / `/step`)**: The AI interacting with the environment (via `inference.py`) issues commands to analyze the current message and reads the full `observation` context (the thread, attachments, priority, etc.).
3. **Execution**: The AI is prompted to output a strict JSON formatted `action` (e.g., `"action_type": "classify_email"` or `"action_type": "archive"`). 
4. **Intermediate Scoring**: The internal logic awards dense rewards instantly. For example, flagging a CEO-level priority correctly might reward `+0.10`, while mistakenly deleting an actionable ticket results in a severe `-0.30` penalty.
5. **Grading (`/grader`)**: At the end of an episode, standard OpenEnv grader logic aggregates the results into a uniform scalar score mapped precisely between `[0.0, 1.0]`.

---

## 🤖 Detailed Agent Documentation (Antigravity AI)

This section acts as a detailed operation manual for the AI Coding Assistant (Antigravity) operating in this workspace. 

### What is the Antigravity Agent?
Antigravity is a deeply integrated AI assistant capable of performing robust multi-step reasoning, directly executing terminal commands, creating and debugging code, and engaging with GSD (Get Stuff Done) workflow milestones naturally. The agent runs alongside the developer within this current working directory.

### Core Capabilities within the MailMind Repository:
- **Direct Refactoring:** You can instruct the agent to update logic formulas (e.g., editing `app/core/rewards.py`) without having to copy-paste. The agent reads the files, performs code replacements in standard Python environments, and verifies syntax on the fly.
- **Terminal Operations:** By granting the agent permission, it can handle dependency building, pip installations, and even run the background server locally (`uvicorn app.main:app`).
- **Running Inference Scripts:** Instead of manually launching evaluations, the agent can be tasked to *"Run the baseline inference test for the Medium task"* by having it execute `python inference.py` assuming standard `.env` variables (`HF_TOKEN` and `API_BASE_URL`) exist.
- **Git State Management:** The agent can be instructed to branch logic, rollback bad decisions, and push updates straight to your remote branch. 
- **Testing & Tooling:** It uses `pytest` locally to confirm whether graders work as intended and `grep` natively to perform broad codebase searches extremely quickly.

### How to Assign Tasks to the Agent:
To effectively work with the agent, follow these conventions linearly in your chat:

1. **Natural Language Requests**: Simply say: *"I want to increase the logging verbosity when an agent deletes a message."* The agent will automatically find where deleting actions are processed, trace logic in `environment.py`, apply the update, and wait.
2. **Running Evaluations**: *"Execute the `inference.py` outputting explicitly what actions failed."* 
3. **Using Automated GSD Workflows**: You can leverage specialized "skills" for project management:
   - Type `/gsd-plan-phase` to break a larger feature (like adding an intermediate difficulty task) into organized roadmap steps.
   - Type `/gsd-execute-phase` to have the agent work uninterrupted on completing those steps autonomously.
   
### Common Instructions
- **Hiding Unused Workspace Files**: Handled intelligently via `.vscode/settings.json` `files.exclude` parameters, allowing you to hide clutter like `.docx` and extraction tests from your file tree. 
- **Automated Pushes**: When wrapping up an update, command: *"Commit everything as 'update evaluations' and push"* to instantly reflect changes to origin.
