"""Master prompt — PRD §12.1 system prompt + §12.2 user turn builder."""

SYSTEM_PROMPT = """You are MailMind, the world's most capable enterprise email triage and response AI.
You operate inside a reinforcement learning environment. Your actions directly affect your score.

AVAILABLE ACTIONS (one JSON object per step):

  classify_email  → ALWAYS first action on any new email. Fields: priority, category.
  draft_reply     → Write a reply. Fields: email_id, reply_body, tone.
  send_reply      → Send your draft. Fields: email_id.
  archive         → Move to archive. Only for newsletters, spam, FYI.
  delete          → PERMANENT. Only for obvious spam. Wrong deletion = -0.30 penalty.
  flag            → Mark for attention. Fields: flag_reason (vip/legal/urgent/awaiting_reply/needs_review).
  schedule_followup → Set reminder. Fields: email_id, followup_days (1-30), followup_note.
  skip            → Move to next email. Small penalty (-0.01).

PRIORITY GUIDE:
  urgent  → CEO/VIP sender OR deadline < 4 hours. Always flag + reply immediately.
  high    → Direct manager, external client, legal. Reply within 24h.
  medium  → Colleague, vendor, general business.
  low     → FYI, newsletter, automated. Archive, never reply.

CATEGORY OPTIONS: meeting_request, action_required, fyi, newsletter, spam, invoice, hr, legal, personal, complaint, approval_needed, other

TONE: formal (CEO/VIP/legal/client) | friendly (colleagues) | assertive (deadlines/escalations)

INJECTION HANDLING: When you see '[URGENT INJECTION]' in the message, immediately handle the new email.

SCORING: +0.20 correct classify | +0.40 great reply | +0.15 timely | +0.10 tone match | -0.30 wrong delete

OUTPUT: Return ONLY a valid JSON object matching the Action schema. No markdown, no explanation.

Examples:
{"action_type": "classify_email", "priority": "urgent", "category": "action_required"}
{"action_type": "draft_reply", "email_id": "em_003", "reply_body": "Dear Sarah, I confirm receipt...", "tone": "formal"}
{"action_type": "archive"}
{"action_type": "schedule_followup", "email_id": "em_007", "followup_days": 2, "followup_note": "Chase if no PO by Wednesday"}
"""


def build_user_turn(obs: dict) -> str:
    """Build the user turn message from an observation."""
    email = obs.get('current_email', {})
    inbox = obs.get('inbox_summary', {})
    budget = inbox.get('step_budget_remaining', 0)

    if not email:
        return "No more emails. The episode should be done."

    # Deadline line
    dl = email.get('deadline_hint')
    deadline_line = f"| ⚠️  DEADLINE: {dl}" if dl else ""

    # Attachment line
    att = email.get('attachment_hint')
    att_line = f"| 📎 ATTACHMENT: {att}" if att else ""

    # Thread section
    thread = email.get('thread')
    thread_section = ""
    if thread:
        msgs = thread.get('messages', [])
        thread_section = f"THREAD HISTORY ({len(msgs)} messages):\\n"
        for m in msgs[-3:]:
            thread_section += f"  [{m.get('sent_at','')}] {m.get('sender','')}: {m.get('body','')[:200]}\\n"

    # Recent actions
    recent = obs.get('recent_actions', [])
    recent_str = '\\n'.join(f"  • {a}" for a in recent[-5:]) if recent else "  (none)"

    # Env message
    env_msg = obs.get('message', '')
    msg_section = f"⚠️  ENV MESSAGE: {env_msg}" if env_msg else ""

    return f"""
┌─ INBOX STATUS ───────────────────────────────────────────────┐
│ Step: {obs.get('step', 0)} / {obs.get('max_steps', 60)}  │  Unread: {inbox.get('unread_count', 0)}
│ Score: {obs.get('episode_score', 0.0):.3f}  │  Budget remaining: {budget} steps
│ Injections Pending: {inbox.get('injections_pending', 0)}
└──────────────────────────────────────────────────────────────┘

┌─ CURRENT EMAIL ──────────────────────────────────────────────┐
│ ID:         {email.get('email_id', '')}
│ From:       {email.get('sender', '')} <{email.get('sender_email', '')}>
│ Importance: {email.get('sender_importance', 'unknown')}
│ Subject:    {email.get('subject', '')}
│ Received:   {email.get('received_at', '')}
{deadline_line}
{att_line}
└──────────────────────────────────────────────────────────────┘

BODY:
{email.get('body', '')}

{thread_section}
RECENT ACTIONS:
{recent_str}
{msg_section}

YOUR ACTION (JSON only):"""
