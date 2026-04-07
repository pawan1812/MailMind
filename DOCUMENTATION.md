# MailMind: Extended Documentation

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
