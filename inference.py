"""
MailMind Inference Script — OpenEnv Hackathon 2025
===================================
MANDATORY ENV VARS:
    API_BASE_URL       The API endpoint for the LLM.
    MODEL_NAME         The model identifier to use for inference.
    HF_TOKEN           Your Hugging Face / API key.
    LOCAL_IMAGE_NAME   The name of the local Docker image (optional, for from_docker_image())

STDOUT FORMAT:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

Runs ALL 3 tasks: classify_inbox (easy), draft_replies (medium), manage_inbox (hard).
"""

import os
import sys
import json
import textwrap
from typing import List, Optional

import httpx
from openai import OpenAI

# ── Required Hackathon Environment Variables ─────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")

# Optional - if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

BENCHMARK = "mailmind"
TASKS = ["classify_inbox", "draft_replies", "manage_inbox"]
MAX_STEPS_PER_TASK = {"classify_inbox": 20, "draft_replies": 30, "manage_inbox": 60}
SEED = 42
TEMPERATURE = 0.2
MAX_TOKENS = 768

# Default env URL — points to the Docker container / HF Space
ENV_URL = os.getenv("OPENENV_BASE_URL", os.getenv("MAILMIND_URL", "http://localhost:7860"))

# ── System Prompt (self-contained — no external imports) ─────────────

SYSTEM_PROMPT = textwrap.dedent("""
You are MailMind, a professional AI email manager. Your job is to process
each email in the inbox efficiently, accurately, and professionally.

DECISION FRAMEWORK:
1. READ the email body, sender role, thread history, attachments.
2. CLASSIFY by priority (urgent|high|medium|low) and category
   (meeting_request|action_required|fyi|newsletter|spam|invoice|hr|legal|personal|complaint|approval_needed|other).
3. DECIDE: If spam → delete. If low + no questions → archive. If questions → draft reply.
   If future follow-up needed → schedule_followup.

TONE RULES:
- CEO/Board → formal   - Client → professional   - Teammate → friendly
- Vendor → professional  - Unknown → professional

PENALTIES: Deleting urgent/high emails (-0.30). Replying to spam (-0.15).
Skipping actionable emails (-0.15). Rude language (-0.20).

OUTPUT: Respond with valid JSON only. No markdown. No preamble.
{
  "action_type": "classify_email|draft_reply|send_reply|archive|delete|flag|schedule_followup|skip",
  "priority": "urgent|high|medium|low",
  "category": "meeting_request|action_required|fyi|...",
  "email_id": "<email_id>",
  "reply_body": "<reply text>",
  "tone": "formal|professional|friendly|brief",
  "followup_days": 3,
  "followup_note": "<note>",
  "flag_reason": "vip|legal|urgent|awaiting_reply|needs_review"
}
Include only the fields relevant to your chosen action_type.
""").strip()


def build_user_turn(obs: dict) -> str:
    """Build the user-turn message from the observation."""
    email = obs.get("current_email")
    if not email:
        return "No more emails. Episode complete."

    summary = obs.get("inbox_summary", {})
    step = obs.get("step", 0)
    recent = obs.get("recent_actions", [])

    parts = [
        f"═══ EMAIL TO PROCESS ═══",
        f"Email ID:    {email.get('email_id', 'N/A')}",
        f"From:        {email.get('sender', 'Unknown')} ({email.get('sender_importance', 'unknown')})",
        f"Subject:     {email.get('subject', '(no subject)')}",
        f"Received:    {email.get('received_at', 'N/A')}",
        f"Attachment:  {email.get('attachment_hint', 'None')}",
        f"Deadline:    {email.get('deadline_hint', 'None')}",
        "",
        "BODY:",
        email.get("body", "(empty)"),
        "",
        f"═══ INBOX ═══",
        f"Step:           {step}",
        f"Total emails:   {summary.get('total_emails', '?')}",
        f"Unread:         {summary.get('unread_count', '?')}",
        f"Processed:      {summary.get('processed_count', '?')}",
        f"Budget left:    {summary.get('step_budget_remaining', '?')}",
    ]

    if email.get("thread") and email["thread"].get("messages"):
        parts.append("")
        parts.append("THREAD HISTORY:")
        for msg in email["thread"]["messages"][-3:]:
            parts.append(f"  [{msg.get('sender', '?')}]: {msg.get('body', '')[:200]}")

    if recent:
        parts.append("")
        parts.append("RECENT ACTIONS:")
        for r in recent[-3:]:
            parts.append(f"  {r}")

    parts.append("")
    parts.append("Respond with valid JSON only.")
    return "\n".join(parts)


# ── Standard Log Formatters ──────────────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    if error:
        err_clean = str(error).replace('\n', ' ').replace('\r', ' ').strip()
        error_val = f'"{err_clean}"'
    else:
        error_val = "null"
    done_val = str(done).lower()
    print(
        f"[STEP]  step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"
    print(
        f"[END]   success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── LLM Call ──────────────────────────────────────────────────────────

def get_model_action(client: OpenAI, messages: List[dict]) -> str:
    """Call LLM and return raw JSON string."""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        text = (completion.choices[0].message.content or "").strip()
        return text if text else '{"action_type": "skip"}'
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", file=sys.stderr, flush=True)
        return '{"action_type": "skip"}'


# ── Run One Episode ──────────────────────────────────────────────────

def run_task(client: OpenAI, http: httpx.Client, task_id: str) -> None:
    """Run one complete episode for a single task with full logging."""
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        # Reset
        reset_resp = http.post(f"{ENV_URL}/reset", json={"task_id": task_id, "seed": SEED})
        reset_resp.raise_for_status()
        session_id = reset_resp.headers.get("X-Session-ID", "default")
        obs = reset_resp.json()

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        headers = {"X-Session-ID": session_id}
        max_steps = MAX_STEPS_PER_TASK.get(task_id, 60)

        while not obs.get("done", False) and steps_taken < max_steps:
            steps_taken += 1

            # Build prompt
            user_turn = build_user_turn(obs)
            messages.append({"role": "user", "content": user_turn})

            # LLM decision
            action_text = get_model_action(client, messages)
            messages.append({"role": "assistant", "content": action_text})

            # Keep context window manageable
            if len(messages) > 12:
                messages = messages[:1] + messages[-10:]

            # Parse action
            error_msg = None
            try:
                action = json.loads(action_text)
                if not isinstance(action, dict):
                    error_msg = f"Model returned {type(action).__name__}, expected dict"
                    action = {"action_type": "skip"}
            except Exception as exc:
                action = {"action_type": "skip"}
                error_msg = str(exc)

            if not action.get("action_type"):
                action["action_type"] = "skip"

            # Step
            step_resp = http.post(f"{ENV_URL}/step", json={"action": action}, headers=headers)
            if step_resp.status_code != 200:
                error_msg = step_resp.text[:200].replace('\n', ' ')
                reward_val = 0.0
                obs["done"] = True
            else:
                result = step_resp.json()
                reward_val = result.get("reward", {}).get("value", 0.0)
                obs = result.get("observation") or obs
                if result.get("done"):
                    obs["done"] = True
                last_error = result.get("info", {}).get("error")
                if last_error:
                    error_msg = last_error

            rewards.append(reward_val)

            action_str = action.get("action_type", "unknown")
            log_step(
                step=steps_taken,
                action=action_str,
                reward=reward_val,
                done=obs.get("done", False),
                error=error_msg,
            )

        # Grade
        grade_resp = http.post(f"{ENV_URL}/grader", headers=headers)
        if grade_resp.status_code == 200:
            score = grade_resp.json().get("final_score", 0.0)

        # Clamp to open interval (0, 1) — bounds chosen to survive :.2f formatting
        # 0.01 formats as "0.01", 0.99 formats as "0.99" — both strictly in (0, 1)
        score = min(0.99, max(0.01, score))
        success = score >= 0.1

    except Exception as e:
        print(f"[DEBUG] Task {task_id} error: {e}", file=sys.stderr, flush=True)

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    http = httpx.Client(timeout=120.0)

    try:
        for task_id in TASKS:
            run_task(client, http, task_id)
    finally:
        http.close()


if __name__ == "__main__":
    main()
