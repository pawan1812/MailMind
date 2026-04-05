"""Jinja2 email body templates — PRD §3.2"""

# Pre-defined email body templates that InboxSimulator can use
# for more realistic emails than pure Faker paragraphs.

TEMPLATES = {
    'meeting_request': [
        """Hi {name},

I'd like to schedule a {meeting_type} to discuss {topic}. Would {day} at {time} work for you?

Please let me know your availability. {extra}

Best regards,
{sender}""",
        """Dear {name},

Following up on our previous conversation about {topic} — can we set up a call this week?
{day} afternoon would work best on my end.

{extra}

Thanks,
{sender}""",
    ],

    'action_required': [
        """Hi {name},

I need your input on the {topic} by {deadline}. Specifically:

1. {question_1}
2. {question_2}

{extra}

Please prioritize this.

Thanks,
{sender}""",
        """Hi {name},

Action needed: The {topic} requires your sign-off before we can proceed.
Deadline: {deadline}

{extra}

Regards,
{sender}""",
    ],

    'fyi': [
        """Hi all,

Just a heads up — {topic}.

No action needed from your side, just keeping you in the loop.

{extra}

Best,
{sender}""",
        """Team,

FYI: {topic}. This was discussed in {meeting_type} last week.

{extra}

Cheers,
{sender}""",
    ],

    'invoice': [
        """Dear {name},

Please find attached Invoice #{invoice_number} for {amount} due by {deadline}.

{extra}

Let me know if you have any questions.

Regards,
{sender}
Accounts Department""",
    ],

    'complaint': [
        """Dear {name},

I'm writing to raise a concern about {topic}. We've experienced {issue_detail} and this is impacting our operations.

I'd appreciate a prompt response and resolution plan.

{extra}

Regards,
{sender}""",
    ],

    'newsletter': [
        """📰 Weekly {topic} Digest

This week's highlights:
• {highlight_1}
• {highlight_2}
• {highlight_3}

Read more at our website. You're receiving this because you subscribed.

Unsubscribe | Manage preferences""",
    ],

    'spam': [
        """CONGRATULATIONS! You've been selected for an exclusive {topic} opportunity!
Click here NOW to claim your {amount} reward!!! Limited time only!!!

Act fast — this expires {deadline}!""",
        """Dear Valued Customer,

We detected unusual activity on your account. Click below to verify:
[VERIFY NOW]

This is an automated message from {sender}.
Do not reply.""",
    ],

    'approval_needed': [
        """Hi {name},

The following item requires your approval:

- Item: {topic}
- Amount: {amount}
- Requested by: {requester}
- Deadline: {deadline}

Please approve or reject in the system.

{extra}

Thanks,
{sender}""",
    ],

    'personal': [
        """Hey {name},

{topic}? Let me know if you're free.

{extra}

Cheers,
{sender}""",
    ],

    'legal': [
        """Dear {name},

Please review the attached {topic}. We need your acknowledgement by {deadline}.

Important: This is a confidential document. Do not forward.

{extra}

Regards,
{sender}
Legal Department""",
    ],
}


def render_template(category: str, variables: dict) -> str:
    """Render a random email body template for the given category."""
    import random
    templates = TEMPLATES.get(category, TEMPLATES['fyi'])
    template = random.choice(templates)
    try:
        return template.format(**variables)
    except KeyError:
        # Fill missing variables with placeholders
        result = template
        import re
        for match in re.finditer(r'\{(\w+)\}', template):
            key = match.group(1)
            if key not in variables:
                variables[key] = f"[{key}]"
        return template.format(**variables)
