# MailMind: Extended Architectural & Operations Guide

## 📌 1. What is MailMind?
MailMind is a production-grade **OpenEnv-compatible Reinforcement Learning Environment** that simulates an enterprise email management ecosystem. Unlike synthetic multiple-choice tests, MailMind forces AI agents to traverse a multi-turn, state-heavy environment. It bridges the gap between text-based reasoning models and practical workflow agents. 

You build an AI agent and connect it to MailMind's HTTP REST Sandbox. Your agent "reads" emails, tracks a "budget" of time (max steps), and emits precise tool commands (JSONs) to classify priorities, formulate corporate-toned replies, schedule calendar follow-ups, and react dynamically to sudden urgent inbox injections (like a sudden server-down alert).

---

## 🏆 2. Project Scores (Baseline Evaluation)
According to the built-in OpenEnv validation baseline runs using **`gpt-4o-mini` (temperature `0.2`)**, here are the base performance benchmarks out of a maximum of **`1.0`**:

| Task ID | Difficulty | Baseline Avg Score | Variance Constraints |
| :--- | :--- | :--- | :--- |
| **`classify_inbox`** | 🟢 Easy | `0.7745` | Standard deviation ~0.04 |
| **`draft_replies`** | 🟡 Medium | `0.5820` | Captures semantics/tone matching |
| **`manage_inbox`** | 🔴 Hard | `0.3855` | Missed deadlines & urgent deletes scale penalties |
| **✨ Global Avg** | --- | **`0.5806`** | --- |

---

## ⚙️ 3. How MailMind Works Inside
At its core, MailMind acts as a state machine simulating time passing, an unread email stack, and user constraints.

### 🔄 The REST Lifecycle
1. **Initialization (`POST /reset`)**
   Your agent requests a new session containing a `task_id` (e.g., `manage_inbox`) and a `seed`. MailMind's **InboxSimulator** engine builds a deterministic inbox using `Faker` and complex Jinja templates, generating between 15-45 emails (newsletters, angry clients, internal HR requests) with hidden "ground truths".

2. **Observation (`GET /state`)**
   MailMind hands your agent an `Observation` context. It includes:
   * **The Current Email Details:** Who sent it, thread history, subject, attachments.
   * **Inbox Meta-State:** Number of emails unread, total steps remaining in the "clock budget", how many high-priority emails exist.

3. **Execution (`POST /step`)**
   The AI reads the Observation and generates a strictly formatted JSON action:
   ```json
   {
      "action_type": "draft_reply",
      "email_id": "em_x29A",
      "reply_body": "Hello John, checking on the Q3 metrics.",
      "tone": "professional"
   }
   ```
   
4. **Intermediate Scoring (Dense Rewards)**
   Instead of waiting roughly 40 turns to tell your AI if it passed, the `RewardCalculator` evaluates every single action immediately via dense rewards bounding between `[-0.5, 0.5]`. 
   * *Example:* Scheduling a follow up in the correct time window yields `+0.15`.
   * *Example:* Deleting an urgent client email triggers a severe penalty `-0.30`.

5. **Final Evaluation (`POST /grader`)**
   At exhaustion (reaching max steps or empty inbox), the OpenEnv grading pipeline consolidates everything—time efficiency, classification mismatches, tone alignments—into one normalized scalar score `[0.0, 1.0]`.

---

## 🌊 4. How to Create an AI Agent Flow for MailMind
If you are designing the AI Agent that connects to MailMind, here is the architectural strategy required to succeed at navigating this flow effectively:

### Step A: System Prompt Design
Your logic model must act as an executive assistant. Pre-prompt the agent with a firm "Decision Framework":
* **Read Phase:** Analyze sender domain (`@gmail.com` vs `@internal.corp`).
* **Categorization Rule:** Immediately guess if this requires scheduling via the calendar or if it is a general broadcast newsletter.
* **Tone enforcement:** "If addressing the CEO, tone MUST be `formal`; if internal peers, use `friendly`."

### Step B: The Agent Loop Process Flow
An optimal custom agent loop inside your inference script should look like this:

1. **Start the Loop (`while not done:`)**
2. **Fetch Screen:** Retrieve `current_email` from the observation list.
3. **Internal Reasoning (Optional but Recommended):** Make your LLM output a raw text "thought" block before dumping the JSON. Have the LLM ask: *“Is this urgent? Yes. Does it need a reply now? No, just scheduled.”*
4. **Commit API Action:** Fire off the `/step` interaction. Parse the dense `reward` value returned.
5. **Adjust Dynamically:** If the environment returns a negative reward `(-0.15)` for an action, inject that feedback into the agent's context history so the agent learns mid-session to not repeat that mistake.

### Step C: Handling "Hard Mode" Dynamics (Dynamic Injections)
During the `manage_inbox` task, emails arrive dynamically—simulating real-time alerts. 
* Your agent must keep an eye on `inbox_summary['unread_count']` spikes. 
* Your flow must support pausing its current linear traversal to prioritize and switch over to resolving incoming `urgent` flag injections (e.g., server down tickets) before deadlines expire, or it will rapidly bleed baseline points.
