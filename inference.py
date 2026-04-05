import asyncio
import os
import sys
import json
from typing import List, Optional

try:
    import httpx
    from openai import OpenAI
except ImportError:
    print("ERROR: Install openai and httpx first: pip install openai httpx")
    sys.exit(1)

from baseline.prompts import SYSTEM_PROMPT, build_user_turn

# ── Required Hackathon Variables ──────────────────────────────────────
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://api.openai.com/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "gpt-4o-mini"
MAILMIND_URL = os.getenv("MAILMIND_URL", "http://localhost:7860")

BENCHMARK = "MailMind"
# Assuming we run the hard task for the official inference run
TASK_NAME = "manage_inbox"
SUCCESS_SCORE_THRESHOLD = 0.3

# ── Standard Log Formatters ──────────────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)

# ── Inference Execution ──────────────────────────────────────────────

def get_model_action(client: OpenAI, messages: List[dict]) -> str:
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.2,
            max_tokens=768,
            response_format={'type': 'json_object'},
        )
        text = (completion.choices[0].message.content or "").strip()
        return text if text else '{"action_type": "skip"}'
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return '{"action_type": "skip"}'

def main() -> None:
    api_key_safe = API_KEY or "sk-dummy_key_for_testing"
    client = OpenAI(base_url=API_BASE_URL, api_key=api_key_safe)
    http = httpx.Client(timeout=60.0)

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        # Reset Environment
        reset_resp = http.post(f"{MAILMIND_URL}/reset", json={"task_id": TASK_NAME, "seed": 42})
        reset_resp.raise_for_status()
        obs = reset_resp.json()

        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]

        while not obs.get('done', False):
            steps_taken += 1
            
            user_turn = build_user_turn(obs)
            messages.append({'role': 'user', 'content': user_turn})

            # LLM Decision
            action_text = get_model_action(client, messages)
            
            # Keep LLM context window manageable
            messages.append({'role': 'assistant', 'content': action_text})
            if len(messages) > 10:
                messages = messages[:1] + messages[-8:]

            try:
                action = json.loads(action_text)
                error_msg = None
            except json.JSONDecodeError as exc:
                action = {'action_type': 'skip'}
                error_msg = str(exc)

            # Step Environment
            step_resp = http.post(f"{MAILMIND_URL}/step", json={"action": action})
            if step_resp.status_code != 200:
                error_msg = step_resp.text
                reward_val = 0.0
                obs['done'] = True
            else:
                result = step_resp.json()
                reward_val = result.get('reward', {}).get('value', 0.0)
                obs = result.get('observation') or obs
                if result.get('done'):
                    obs['done'] = True

            rewards.append(reward_val)
            
            # Condense action string for logs (prevent massive JSON dumps on one line)
            action_str = f"{action.get('action_type', 'unknown')}:{action.get('email_id', 'none')}"

            log_step(
                step=steps_taken, 
                action=action_str, 
                reward=reward_val, 
                done=obs.get('done', False), 
                error=error_msg
            )

        # Post-episode Grader call
        grade_resp = http.post(f"{MAILMIND_URL}/grader")
        if grade_resp.status_code == 200:
            score = grade_resp.json().get('final_score', 0.0)
        
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as e:
        print(f"[DEBUG] Execution error: {e}", flush=True)
    finally:
        http.close()
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

if __name__ == "__main__":
    main()
