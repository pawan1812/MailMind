"""Final comprehensive verification — tests every endpoint, action, edge case."""
import httpx, json, sys, time

BASE = "http://localhost:7862"
P, F, ERRS = 0, 0, []

def t(name, cond, detail=""):
    global P, F
    if cond: P += 1; print(f"  [PASS] {name}")
    else: F += 1; ERRS.append(f"{name}: {detail}"); print(f"  [FAIL] {name} -- {detail}")

def main():
    global P, F
    h = httpx.Client(timeout=30.0)

    print("\n" + "="*65)
    print("  MailMind v2.0 -- FINAL Comprehensive Verification")
    print("="*65)

    # ==================== HEALTH ====================
    print("\n--- [1] GET /health ---")
    r = h.get(f"{BASE}/health")
    t("Returns 200", r.status_code == 200)
    d = r.json()
    t("Version 2.0.0", d.get("version") == "2.0.0")
    t("Status healthy", d.get("status") == "healthy")
    t("Firebase field present", "firebase" in d)
    t("Uptime > 0", d.get("uptime_seconds", 0) > 0)

    # ==================== TASKS ====================
    print("\n--- [2] GET /tasks ---")
    r = h.get(f"{BASE}/tasks")
    t("Returns 200", r.status_code == 200)
    tasks = r.json()
    t("3 tasks", len(tasks) == 3)
    for tk in tasks:
        t(f"Task '{tk['id']}' has all fields",
          all(k in tk for k in ['id','name','difficulty','max_steps','description','action_types','grader']))

    # ==================== BASELINE ====================
    print("\n--- [3] POST /baseline ---")
    r = h.post(f"{BASE}/baseline")
    t("Returns 200", r.status_code == 200)
    bl = r.json()
    t("Has model", "model" in bl)
    t("Has 3 task scores", len(bl.get("scores", {})) == 3)
    t("Has average", "average" in bl)

    # ==================== OPENENV.YAML ====================
    print("\n--- [4] GET /openenv.yaml ---")
    r = h.get(f"{BASE}/openenv.yaml")
    t("Returns 200", r.status_code == 200)
    t("Has mailmind", "mailmind" in r.text.lower())
    t("Has version 2.0.0", "2.0.0" in r.text)
    t("Has 3 tasks", r.text.count("- id:") == 3)

    # ==================== EASY TASK: FULL EPISODE ====================
    print("\n--- [5] POST /reset -- classify_inbox (EASY) ---")
    r = h.post(f"{BASE}/reset", json={{"task_id": "classify_inbox", "seed": 42}})
    t("Returns 200", r.status_code == 200)
    obs = r.json()
    t("episode_id starts with ep_", obs.get("episode_id","").startswith("ep_"))
    t("step=0", obs.get("step") == 0)
    t("done=false", obs.get("done") == False)
    em = obs.get("current_email", {{}})
    t("Email has email_id", "email_id" in em)
    t("Email has subject", len(em.get("subject","")) > 3)
    t("Email has sender", len(em.get("sender","")) > 1)
    t("Email has sender_email", "@" in em.get("sender_email",""))
    t("Email has sender_domain", "." in em.get("sender_domain",""))
    t("Email has sender_importance", em.get("sender_importance") in
      ['ceo','vip','direct_manager','colleague','external_client','vendor','unknown','spam_likely'])
    t("Email has body > 10 chars", len(em.get("body","")) > 10)
    t("Email has received_at", "received_at" in em)
    t("Email has has_attachment", "has_attachment" in em)
    t("Email has deadline_hint field", "deadline_hint" in em)
    t("Email has cc_count", "cc_count" in em)
    summ = obs.get("inbox_summary", {{}})
    t("total_emails=15", summ.get("total_emails") == 15)
    t("unread_count=15", summ.get("unread_count") == 15)
    t("processed_count=0", summ.get("processed_count") == 0)
    t("step_budget_remaining=20", summ.get("step_budget_remaining") == 20)
    t("categories is dict", isinstance(summ.get("categories"), dict))
    t("Has timestamp", "timestamp" in obs)

    # ---- All 8 action types ----
    print("\n--- [6] ALL 8 ACTION TYPES ---")

    # 6a. classify_email
    print("  >> classify_email")
    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "classify_email", "priority": "medium", "category": "personal"}}}})
    t("classify returns 200", r.status_code == 200)
    res = r.json()
    rw = res.get("reward", {{}})
    t("Reward value is float", isinstance(rw.get("value"), (int, float)))
    t("Reward cumulative is float", isinstance(rw.get("cumulative"), (int, float)))
    bd = rw.get("breakdown", {{}})
    t("12 breakdown keys", len(bd) == 12, f"got {{len(bd)}}")
    t("reason string", len(rw.get("reason","")) > 0)
    t("step number in reward", "step" in rw)
    t("Reward capped [-0.5, 0.5]", -0.5 <= rw.get("value",0) <= 0.5)
    t("observation returned", res.get("observation") is not None)
    t("done=false", res.get("done") == False)

    # 6b. archive
    print("  >> archive")
    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "archive"}}}})
    t("archive returns 200", r.status_code == 200)
    bd = r.json().get("reward",{{}}).get("breakdown",{{}})
    t("archive_correctness in breakdown", "archive_correctness" in bd)

    # 6c. skip
    print("  >> skip")
    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "skip"}}}})
    t("skip returns 200", r.status_code == 200)
    t("waste penalty = -0.01", r.json().get("reward",{{}}).get("breakdown",{{}}).get("step_waste_penalty") == -0.01)

    # 6d. flag
    print("  >> flag")
    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "flag", "flag_reason": "vip"}}}})
    t("flag returns 200", r.status_code == 200)

    # 6e. draft_reply
    print("  >> draft_reply")
    cur = r.json().get("observation",{{}}).get("current_email",{{}})
    eid = cur.get("email_id", "em_004") if cur else "em_004"
    r = h.post(f"{BASE}/step", json={{"action": {{
        "action_type": "draft_reply", "email_id": eid,
        "reply_body": "Thank you for your email. I will review and get back to you by end of day.",
        "tone": "formal"
    }}}})
    t("draft_reply returns 200", r.status_code == 200)
    bd = r.json().get("reward",{{}}).get("breakdown",{{}})
    t("reply_relevance populated", "reply_relevance" in bd)
    t("tone_match populated", "tone_match" in bd)

    # 6f. send_reply
    print("  >> send_reply")
    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "send_reply", "email_id": eid}}}})
    t("send_reply returns 200", r.status_code == 200)
    t("timeliness_bonus in breakdown", "timeliness_bonus" in r.json().get("reward",{{}}).get("breakdown",{{}}))

    # 6g. schedule_followup
    print("  >> schedule_followup")
    cur = r.json().get("observation",{{}}).get("current_email",{{}})
    eid2 = cur.get("email_id", "em_006") if cur else "em_006"
    r = h.post(f"{BASE}/step", json={{"action": {{
        "action_type": "schedule_followup", "email_id": eid2,
        "followup_days": 3, "followup_note": "Chase by Wednesday"
    }}}})
    t("schedule_followup returns 200", r.status_code == 200)
    t("followup_quality populated", "followup_quality" in r.json().get("reward",{{}}).get("breakdown",{{}}))

    # 6h. delete
    print("  >> delete")
    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "delete"}}}})
    t("delete returns 200", r.status_code == 200)
    t("wrong_delete_penalty populated", "wrong_delete_penalty" in r.json().get("reward",{{}}).get("breakdown",{{}}))

    # ---- State check ----
    print("\n--- [7] GET /state ---")
    r = h.get(f"{BASE}/state")
    t("Returns 200", r.status_code == 200)
    st = r.json()
    t("episode_id present", "episode_id" in st)
    t("task_id = classify_inbox", st.get("task_id") == "classify_inbox")
    t("step >= 8", st.get("step", 0) >= 8)
    t("cumulative_reward is float", isinstance(st.get("cumulative_reward"), (int, float)))
    t("classifications dict", isinstance(st.get("classifications"), dict))
    t("processed_count > 0", st.get("processed_count", 0) > 0)
    t("drafts_count tracked", "drafts_count" in st)
    t("archives_count tracked", "archives_count" in st)

    # ---- Grader ----
    print("\n--- [8] POST /grader ---")
    r = h.post(f"{BASE}/grader")
    t("Returns 200", r.status_code == 200)
    gr = r.json()
    t("final_score in [0,1]", 0.0 <= gr.get("final_score", -1) <= 1.0)
    t("episode_id matches", gr.get("episode_id") == st.get("episode_id"))
    t("task_id matches", gr.get("task_id") == "classify_inbox")
    cs = gr.get("component_scores", {{}})
    for comp in ['classification', 'reply', 'archive', 'followup', 'injection']:
        t(f"component '{comp}'", comp in cs)
    t("weighted_scores present", isinstance(gr.get("weighted_scores"), dict))
    pens = gr.get("penalties", {{}})
    t("penalties present", isinstance(pens, dict))
    for pk in ['redundant_steps', 'missed_deadlines', 'wrong_deletes']:
        t(f"penalty '{pk}'", pk in pens)
    t("efficiency_ratio in [0,1]", 0 <= gr.get("efficiency_ratio", -1) <= 1.0)
    t("total_steps_used > 0", gr.get("total_steps_used", 0) > 0)
    t("step_budget = 20", gr.get("step_budget") == 20)

    # ==================== MEDIUM TASK ====================
    print("\n--- [9] POST /reset -- draft_replies (MEDIUM) ---")
    r = h.post(f"{BASE}/reset", json={{"task_id": "draft_replies", "seed": 42}})
    t("Returns 200", r.status_code == 200)
    obs = r.json()
    t("25 emails", obs.get("inbox_summary",{{}}).get("total_emails") == 25)
    t("Budget 30", obs.get("inbox_summary",{{}}).get("step_budget_remaining") == 30)

    # ==================== HARD TASK + INJECTION ====================
    print("\n--- [10] POST /reset -- manage_inbox (HARD) ---")
    r = h.post(f"{BASE}/reset", json={{"task_id": "manage_inbox", "seed": 42}})
    t("Returns 200", r.status_code == 200)
    obs = r.json()
    t("40 emails", obs.get("inbox_summary",{{}}).get("total_emails") == 40)
    t("Budget 60", obs.get("inbox_summary",{{}}).get("step_budget_remaining") == 60)

    print("\n--- [11] INJECTION TEST (10 steps on hard) ---")
    injection_msg = None
    for i in range(11):
        r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "classify_email", "priority": "medium", "category": "fyi"}}}})
        obs_data = r.json().get("observation")
        if obs_data and obs_data.get("message"):
            injection_msg = obs_data.get("message")
    st = h.get(f"{BASE}/state").json()
    t("Step >= 11", st.get("step", 0) >= 11)
    t("Injection message received", injection_msg is not None and "INJECTION" in (injection_msg or ""),
      f"got: {{injection_msg}}")

    # ==================== VALIDATION ERRORS ====================
    print("\n--- [12] VALIDATION ERRORS ---")
    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "classify_email"}}}})
    t("Missing required fields -> 422", r.status_code == 422)

    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "draft_reply"}}}})
    t("draft_reply without email_id -> 422", r.status_code == 422)

    r = h.post(f"{BASE}/reset", json={{"task_id": "fake_task"}})
    t("Invalid task_id -> 422", r.status_code == 422)

    r = h.post(f"{BASE}/step", json={{"action": {{"action_type": "invalid_type"}}}})
    t("Invalid action_type -> 422", r.status_code == 422)

    # ==================== DETERMINISTIC SEEDING ====================
    print("\n--- [13] DETERMINISTIC SEEDING ---")
    r1 = h.post(f"{BASE}/reset", json={{"task_id": "classify_inbox", "seed": 99}})
    sub1 = r1.json().get("current_email",{{}}).get("subject","")
    r2 = h.post(f"{BASE}/reset", json={{"task_id": "classify_inbox", "seed": 99}})
    sub2 = r2.json().get("current_email",{{}}).get("subject","")
    t("Same seed -> same email", sub1 == sub2 and len(sub1) > 0, f"'{sub1}' vs '{sub2}'")

    r3 = h.post(f"{BASE}/reset", json={{"task_id": "classify_inbox", "seed": 1}})
    sub3 = r3.json().get("current_email",{{}}).get("subject","")
    t("Different seed -> different email", sub1 != sub3, f"both: '{sub1}'")

    # ==================== SESSION ISOLATION ====================
    print("\n--- [14] SESSION ISOLATION ---")
    r_a = h.post(f"{BASE}/reset", json={{"task_id": "classify_inbox", "seed": 42}},
                 headers={{"X-Session-ID": "session_A"}})
    t("Session A reset -> 200", r_a.status_code == 200)
    ep_a = r_a.json().get("episode_id")

    r_b = h.post(f"{BASE}/reset", json={{"task_id": "draft_replies", "seed": 42}},
                 headers={{"X-Session-ID": "session_B"}})
    t("Session B reset -> 200", r_b.status_code == 200)
    ep_b = r_b.json().get("episode_id")
    t("Different episodes", ep_a != ep_b)

    st_a = h.get(f"{BASE}/state", headers={{"X-Session-ID": "session_A"}}).json()
    st_b = h.get(f"{BASE}/state", headers={{"X-Session-ID": "session_B"}}).json()
    t("Session A is classify_inbox", st_a.get("task_id") == "classify_inbox")
    t("Session B is draft_replies", st_b.get("task_id") == "draft_replies")

    # ==================== NO SESSION -> ERROR ====================
    print("\n--- [15] EDGE: /grader with no episode ---")
    r = h.post(f"{BASE}/reset", json={{"task_id": "classify_inbox", "seed": 42}},
               headers={{"X-Session-ID": "fresh_session"}})
    # Step once -> immediate grading
    h.post(f"{BASE}/step", json={{"action": {{"action_type": "classify_email", "priority": "low", "category": "spam"}}}},
           headers={{"X-Session-ID": "fresh_session"}})
    r = h.post(f"{BASE}/grader", headers={{"X-Session-ID": "fresh_session"}})
    t("Grader works on active episode", r.status_code == 200)

    # ==================== SUMMARY ====================
    print("\n" + "="*65)
    total = P + F
    print(f"  RESULTS: {{P}} passed, {{F}} failed out of {{total}} tests")
    print("="*65)
    if ERRS:
        print("\n  FAILURES:")
        for e in ERRS:
            print(f"    [FAIL] {{e}}")
    print()
    h.close()
    return F == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
