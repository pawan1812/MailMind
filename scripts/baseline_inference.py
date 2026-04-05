import os
import requests
import json
import logging
import argparse
import datetime
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

API_URL = "http://localhost:7860"
# Assumes OPENAI_API_KEY environment variable is set
client = OpenAI()

SYSTEM_PROMPT = """
You are MailMind, a professional AI email manager working on behalf of a senior business executive. Your job is to process each email in the inbox efficiently, accurately, and professionally.

CURRENT TASK: {task_id}
STEP: {step_number} / {max_steps}
INBOX REMAINING: {inbox_count} emails
CURRENT SYSTEM TIME (Simulation Time): {current_time}

DECISION FRAMEWORK:
1. Classify the email (urgent, high, normal, low, spam). 
2. Category: client, internal, vendor, hr, finance, legal, personal, spam.
3. Draft a reply ONLY IF an action/question is asked. Tone: formal, professional, friendly, brief. Extract any key entities needed.
4. Schedule follow-ups if expected logic specifies times. Use the Current System Time to calculate the relative "follow_up_in" hours delta mathematically.
5. If an email is low priority and needs no reply, always archive it! If it's a high/urgent priority do NOT delete it.

OUTPUT FORMAT - STRICT JSON:
{{
  "reasoning": "Explain step-by-step your tone choice, classification, and calculation for schedule delta (e.g. Current Time is Wed, Next Tuesday is +144 hrs).",
  "email_id": "{email_id}",
  "classify": {{ "priority": "urgent", "category": "client", "tags": [] }},
  "reply": null, 
  "archive": null, 
  "delete": null, 
  "schedule": null, 
  "skip": null
}}
"""

def get_action_for_email(obs: dict) -> dict:
    current_email = obs["current_email"]
    email_id = current_email["email_id"]
    
    # We simulate starting the environment on a 'Monday' at 9 AM for consistent tests
    simulated_date = datetime.datetime.now().replace(hour=9, minute=0, second=0)
    
    prompt = SYSTEM_PROMPT.format(
        task_id=obs["task_id"],
        step_number=obs["step_number"],
        max_steps=obs["step_number"] + obs["time_remaining"],
        inbox_count=obs["inbox_count"],
        current_time=simulated_date.strftime("%Y-%m-%d %H:%M:%S (%A)"),
        email_id=email_id
    )
    
    user_msg = f"""
    EMAIL ID: {email_id}
    FROM: {current_email["sender_name"]} <{current_email["sender"]}>
    ROLE: {current_email.get("sender_role", "Unknown")}
    SUBJECT: {current_email["subject"]}
    BODY: {current_email["body"]}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.0
        )
        data = json.loads(response.choices[0].message.content)
        logging.info(f"LLM Reasoning: {data.get('reasoning')}")
        return data
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        # Baseline fallback
        return {
            "email_id": email_id,
            "classify": {"priority": "normal", "category": "internal", "tags": []},
            "skip": {"email_id": email_id}
        }

def run_episode(task_id: str):
    logging.info(f"Starting {task_id}")
    res = requests.post(f"{API_URL}/reset?task_id={task_id}")
    res.raise_for_status()
    
    session_id = res.headers.get("x-session-id")
    if not session_id:
        logging.error("No session_id returned by /reset")
        return
        
    obs = res.json()
    done = False
    
    while not done:
        action = get_action_for_email(obs)
        step_res = requests.post(f"{API_URL}/step?session_id={session_id}", json=action)
        step_res.raise_for_status()
        
        step_data = step_res.json()
        done = step_data["done"]
        obs = step_data.get("observation")
        
        reward = step_data.get("reward")
        print(f"Step Reward: {reward['total']} | Breakdown: {reward['breakdown']}")
        
    # Get final grader
    grader = requests.post(f"{API_URL}/grader", params={"session_id": session_id})
    score_data = grader.json()
    logging.info(f"Episode Done. Score: {score_data}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="task1_classify")
    args = parser.parse_args()
    
    if os.getenv("OPENAI_API_KEY"):
        run_episode(args.task)
    else:
        logging.error("OPENAI_API_KEY not set. Cannot run actual baseline.")
