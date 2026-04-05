"""Comprehensive MailMind v2.0 verification script.
Tests every endpoint and every action type end-to-end.
"""
import httpx
import json
import sys

BASE = "http://localhost:7861"
PASS = 0
FAIL = 0
ERRORS = []

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} -- {detail}")

def main():
    global PASS, FAIL
    http = httpx.Client(timeout=30.0)

    print("\n" + "="*65)
    print("  MailMind v2.0 -- Comprehensive Verification")
    print("="*65)

    # -- 1. Health Check --
    print("\n[1] GET /health")
    r = http.get(f"{BASE}/health")
    test("Health returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    test("Version is 2.0.0", data.get("version") == "2.0.0", f"got {data.get('version')}")
    test("Status is healthy", data.get("status") == "healthy")
    test("Firebase status present", "firebase" in data)

    # -- 2. Tasks --
    print("\n[2] GET /tasks")
    r = http.get(f"{BASE}/tasks")
    test("Tasks returns 200", r.status_code == 200)
    tasks = r.json()
    test("3 tasks defined", len(tasks) == 3, f"got {len(tasks)}")
    ids = [t["id"] for t in tasks]
    test("classify_inbox exists", "classify_inbox" in ids)
    test("draft_replies exists", "draft_replies" in ids)
    test("manage_inbox exists", "manage_inbox" in ids)
    test("Easy task has 20 max_steps", tasks[0].get("max_steps") == 20)
    test("Medium task has 30 max_steps", tasks[1].get("max_steps") == 30)
    test("Hard task has 60 max_steps", tasks[2].get("max_steps") == 60)

    # -- 3. Reset (Easy) --
    print("\n[3] POST /reset -- classify_inbox")
    r = http.post(f"{BASE}/reset", json={"task_id": "classify_inbox", "seed": 42})
    test("Reset returns 200", r.status_code == 200, f"got {r.status_code}")
    obs = r.json()
    test("episode_id assigned", "episode_id" in obs and obs["episode_id"].startswith("ep_"))
    test("step is 0", obs.get("step") == 0)
    test("current_email present", obs.get("current_email") is not None)
    email = obs["current_email"]
    test("Email has email_id", "email_id" in email)
    test("Email has sender_importance", "sender_importance" in email)
    test("Email has body", len(email.get("body", "")) > 10)
    test("Email has deadline_hint field", "deadline_hint" in email)
    test("Email has sender_email", "sender_email" in email)
    test("Email has sender_domain", "sender_domain" in email)
    summary = obs.get("inbox_summary", {})
    test("InboxSummary has total_emails=15", summary.get("total_emails") == 15)
    test("InboxSummary has step_budget_remaining=20", summary.get("step_budget_remaining") == 20)
    test("InboxSummary has categories dict", isinstance(summary.get("categories"), dict))
    test("InboxSummary has unread_count", "unread_count" in summary)
    test("InboxSummary has processed_count", "processed_count" in summary)
    test("done is False", obs.get("done") == False)

    # -- 4. Step: classify_email --
    print("\n[4] POST /step -- classify_email")
    r = http.post(f"{BASE}/step", json={
        "action": {"action_type": "classify_email", "priority": "medium", "category": "personal"}
    })
    test("Step returns 200", r.status_code == 200, f"got {r.status_code}")
    result = r.json()
    reward = result.get("reward", {})
    test("Reward has value", "value" in reward)
    test("Reward has cumulative", "cumulative" in reward)
    test("Reward has breakdown", "breakdown" in reward)
    test("Reward has reason string", "reason" in reward and len(reward["reason"]) > 0)
    test("Reward has step number", "step" in reward)
    bd = reward.get("breakdown", {})
    test("Breakdown has 12 components", len(bd) == 12, f"got {len(bd)} keys: {list(bd.keys())}")
    expected_keys = [
        "classification_accuracy", "reply_relevance", "tone_match",
        "timeliness_bonus", "archive_correctness", "flag_correctness",
        "followup_quality", "injection_response", "wrong_delete_penalty",
        "redundant_action_penalty", "missed_deadline_penalty", "step_waste_penalty"
    ]
    for k in expected_keys:
        test(f"  Breakdown has '{k}'", k in bd, f"missing from {list(bd.keys())}")
    test("done is False after 1 step", result.get("done") == False)
    test("observation returned", result.get("observation") is not None)

    # -- 5. Step: archive --
    print("\n[5] POST /step -- archive")
    r = http.post(f"{BASE}/step", json={"action": {"action_type": "archive"}})
    test("Archive returns 200", r.status_code == 200)

    # -- 6. Step: skip --
    print("\n[6] POST /step -- skip")
    r = http.post(f"{BASE}/step", json={"action": {"action_type": "skip"}})
    test("Skip returns 200", r.status_code == 200)
    rd = r.json().get("reward", {})
    test("Skip has -0.01 waste penalty", rd.get("breakdown", {}).get("step_waste_penalty") == -0.01)

    # -- 7. Step: flag --
    print("\n[7] POST /step -- flag")
    r = http.post(f"{BASE}/step", json={
        "action": {"action_type": "flag", "flag_reason": "vip"}
    })
    test("Flag returns 200", r.status_code == 200)

    # -- 8. Step: draft_reply --
    print("\n[8] POST /step -- draft_reply")
    obs_now = r.json().get("observation", {})
    em_id = obs_now.get("current_email", {}).get("email_id", "em_004") if obs_now else "em_004"
    r = http.post(f"{BASE}/step", json={
        "action": {
            "action_type": "draft_reply",
            "email_id": em_id,
            "reply_body": "Thank you for your email. I will review and get back to you shortly.",
            "tone": "formal"
        }
    })
    test("Draft reply returns 200", r.status_code == 200, f"got {r.status_code}")

    # -- 9. Step: send_reply --
    print("\n[9] POST /step -- send_reply")
    r = http.post(f"{BASE}/step", json={
        "action": {"action_type": "send_reply", "email_id": em_id}
    })
    test("Send reply returns 200", r.status_code == 200)

    # -- 10. Step: schedule_followup --
    print("\n[10] POST /step -- schedule_followup")
    obs_now = r.json().get("observation", {})
    em_id2 = obs_now.get("current_email", {}).get("email_id", "em_006") if obs_now else "em_006"
    r = http.post(f"{BASE}/step", json={
        "action": {"action_type": "schedule_followup", "email_id": em_id2,
                   "followup_days": 3, "followup_note": "Check back Wednesday"}
    })
    test("Schedule followup returns 200", r.status_code == 200)

    # -- 11. Step: delete --
    print("\n[11] POST /step -- delete")
    r = http.post(f"{BASE}/step", json={"action": {"action_type": "delete"}})
    test("Delete returns 200", r.status_code == 200)

    # -- 12. GET /state --
    print("\n[12] GET /state")
    r = http.get(f"{BASE}/state")
    test("State returns 200", r.status_code == 200)
    state = r.json()
    test("State has episode_id", "episode_id" in state)
    test("State has step counter", "step" in state)
    test("State has cumulative_reward", "cumulative_reward" in state)
    test("State has classifications", "classifications" in state)
    test("State has processed_count", "processed_count" in state)
    test("Step > 0 after actions", state.get("step", 0) > 0)
    test("Processed emails > 0", state.get("processed_count", 0) > 0)

    # -- 13. POST /grader --
    print("\n[13] POST /grader")
    r = http.post(f"{BASE}/grader")
    test("Grader returns 200", r.status_code == 200)
    grade = r.json()
    test("Grader has final_score", "final_score" in grade)
    test("Final score is float 0-1", 0.0 <= grade.get("final_score", -1) <= 1.0)
    test("Grader has component_scores", "component_scores" in grade)
    cs = grade.get("component_scores", {})
    test("Component: classification", "classification" in cs)
    test("Component: reply", "reply" in cs)
    test("Component: archive", "archive" in cs)
    test("Component: followup", "followup" in cs)
    test("Component: injection", "injection" in cs)
    test("Grader has weighted_scores", "weighted_scores" in grade)
    test("Grader has penalties", "penalties" in grade)
    test("Grader has efficiency_ratio", "efficiency_ratio" in grade)
    test("Grader has total_steps_used", "total_steps_used" in grade)
    test("Grader has step_budget", "step_budget" in grade)

    # -- 14. POST /baseline --
    print("\n[14] POST /baseline")
    r = http.post(f"{BASE}/baseline")
    test("Baseline returns 200", r.status_code == 200)
    bl = r.json()
    test("Baseline has scores", "scores" in bl)
    test("Baseline has model name", "model" in bl)
    test("Baseline has average", "average" in bl)

    # -- 15. Reset (Medium) --
    print("\n[15] POST /reset -- draft_replies (medium)")
    r = http.post(f"{BASE}/reset", json={"task_id": "draft_replies", "seed": 42})
    test("Medium reset returns 200", r.status_code == 200)
    obs = r.json()
    test("Medium has 25 emails", obs.get("inbox_summary", {}).get("total_emails") == 25)
    test("Medium budget is 30", obs.get("inbox_summary", {}).get("step_budget_remaining") == 30)

    # -- 16. Reset (Hard) --
    print("\n[16] POST /reset -- manage_inbox (hard)")
    r = http.post(f"{BASE}/reset", json={"task_id": "manage_inbox", "seed": 42})
    test("Hard reset returns 200", r.status_code == 200)
    obs = r.json()
    test("Hard has 40 emails", obs.get("inbox_summary", {}).get("total_emails") == 40)
    test("Hard budget is 60", obs.get("inbox_summary", {}).get("step_budget_remaining") == 60)

    # -- 17. Injection test (hard task) --
    print("\n[17] Dynamic Injection Test (hard task)")
    for i in range(11):
        r = http.post(f"{BASE}/step", json={
            "action": {"action_type": "classify_email", "priority": "medium", "category": "fyi"}
        })
    state_r = http.get(f"{BASE}/state").json()
    test("Step counter >= 11", state_r.get("step", 0) >= 11)

    # -- 18. Validation Errors --
    print("\n[18] Validation Error Tests")
    r = http.post(f"{BASE}/step", json={
        "action": {"action_type": "classify_email"}
    })
    test("Missing classify fields returns 422", r.status_code == 422, f"got {r.status_code}")

    r = http.post(f"{BASE}/reset", json={"task_id": "nonexistent_task"})
    test("Invalid task returns 422", r.status_code == 422, f"got {r.status_code}")

    # -- 19. openenv.yaml --
    print("\n[19] GET /openenv.yaml")
    r = http.get(f"{BASE}/openenv.yaml")
    test("openenv.yaml returns 200", r.status_code == 200, f"got {r.status_code}")
    test("Contains 'mailmind'", "mailmind" in r.text.lower())
    test("Contains version 2.0.0", "2.0.0" in r.text)

    # -- 20. Deterministic seeding --
    print("\n[20] Deterministic Seeding Test")
    r1 = http.post(f"{BASE}/reset", json={"task_id": "classify_inbox", "seed": 99})
    email1 = r1.json().get("current_email", {}).get("subject", "")
    r2 = http.post(f"{BASE}/reset", json={"task_id": "classify_inbox", "seed": 99})
    email2 = r2.json().get("current_email", {}).get("subject", "")
    test("Same seed = same first email subject", email1 == email2, f"'{email1}' vs '{email2}'")

    # -- SUMMARY --
    print("\n" + "="*65)
    total = PASS + FAIL
    print(f"  RESULTS: {PASS} passed, {FAIL} failed out of {total} tests")
    print("="*65)

    if ERRORS:
        print("\n  FAILURES:")
        for e in ERRORS:
            print(f"    [FAIL] {e}")

    print()
    http.close()
    return FAIL == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
