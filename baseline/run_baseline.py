"""MailMind Baseline Inference Script — PRD §14.
Usage: set OPENAI_API_KEY=sk-... && python -m baseline.run_baseline
"""

import os
import sys
import json
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import httpx
    from openai import OpenAI
except ImportError:
    print("ERROR: Install openai and httpx first:")
    print("  pip install openai httpx")
    sys.exit(1)

from baseline.prompts import SYSTEM_PROMPT, build_user_turn

URL = os.getenv('MAILMIND_URL', 'http://localhost:7860')
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
TEMP = 0.2
MAX_TOKENS = 768


def run_episode(http: httpx.Client, client: OpenAI, task_id: str, seed: int = 42) -> dict:
    """Run one complete episode."""
    # 1. Reset
    resp = http.post(f'{URL}/reset', json={'task_id': task_id, 'seed': seed})
    resp.raise_for_status()
    obs = resp.json()
    print(f"  Episode {obs.get('episode_id')} started — {len(obs.get('inbox_summary', {}).get('total_emails', 0))} emails")

    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    step = 0

    # 2. Step loop
    while not obs.get('done', False):
        user_turn = build_user_turn(obs)
        messages.append({'role': 'user', 'content': user_turn})

        t0 = time.perf_counter()
        try:
            completion = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=TEMP,
                max_tokens=MAX_TOKENS,
                response_format={'type': 'json_object'},
            )
            action_text = completion.choices[0].message.content
        except Exception as e:
            print(f"    LLM error: {e}")
            action_text = '{"action_type": "skip"}'

        latency = time.perf_counter() - t0

        try:
            action = json.loads(action_text)
        except json.JSONDecodeError:
            action = {'action_type': 'skip'}

        messages.append({'role': 'assistant', 'content': action_text})
        if len(messages) > 22:
            messages = messages[:1] + messages[-20:]

        step_resp = http.post(f'{URL}/step', json={'action': action})
        step_resp.raise_for_status()
        result = step_resp.json()

        reward_val = result.get('reward', {}).get('value', 0)
        print(f"    Step {step:3d}: {action.get('action_type', '?'):20s} → reward {reward_val:+.3f}  ({int(latency*1000)}ms)")

        obs = result.get('observation') or obs
        if result.get('done'):
            obs['done'] = True
        step += 1

    # 3. Grade
    grade_resp = http.post(f'{URL}/grader')
    grade_resp.raise_for_status()
    return grade_resp.json()


def main():
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("ERROR: Set OPENAI_API_KEY environment variable first.")
        print("  set OPENAI_API_KEY=sk-...")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    http = httpx.Client(timeout=60.0)

    tasks = ['classify_inbox', 'draft_replies', 'manage_inbox']

    print(f"\n{'='*60}")
    print(f"  MailMind Baseline  |  Model: {MODEL}")
    print(f"{'='*60}")

    results = {}
    for task in tasks:
        print(f"\n  [{task}]")
        result = run_episode(http, client, task_id=task, seed=42)
        score = result.get('final_score', 0.0)
        results[task] = score
        print(f"  → Final Score: {score:.4f}")
        comps = result.get('component_scores', {})
        for k, v in comps.items():
            print(f"     {k:20s}: {v:.4f}")

    print(f"\n{'─'*60}")
    avg = sum(results.values()) / len(results) if results else 0
    print(f"  {'AVERAGE':25s}  {avg:.4f}")
    print(f"{'='*60}\n")

    http.close()
    return results


if __name__ == '__main__':
    main()
