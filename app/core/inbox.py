"""InboxSimulator — PRD §7. Generates synthetic enterprise inboxes with adversarial patterns."""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from faker import Faker
from app.models.observation import Email, EmailThread, ThreadMessage

SUBJECT_TEMPLATES = {
    'meeting_request': [
        'Quick sync re: {project} — {day}?',
        'Reschedule: {project} kickoff to {day}',
        'Can we meet {day} to discuss {topic}?',
        'Team standup — {day} at {time}',
    ],
    'action_required': [
        'ACTION NEEDED: {project} sign-off by {date}',
        'Please review and approve: {document}',
        'URGENT: {topic} requires your input',
        'Follow-up required: {project} deliverables',
    ],
    'fyi': [
        'FYI: {project} status update',
        'Company all-hands recap — {date}',
        'New {topic} policy effective {date}',
    ],
    'newsletter': [
        '{company} Weekly Digest — {date}',
        'Your {topic} newsletter for {month}',
        'Highlights from {community} this week',
    ],
    'spam': [
        'You have been selected for an exclusive offer!',
        'Congratulations! Claim your prize today',
        'Final notice: Update your account information',
    ],
    'invoice': [
        'Invoice #{number} from {company} — Due {date}',
        'Payment reminder: Invoice #{number} overdue',
        'Receipt: Your {service} subscription renewal',
    ],
    'hr': [
        'New WFH Policy 2026',
        'Benefits enrollment deadline: {date}',
        'Team outing: RSVP by {day}',
    ],
    'legal': [
        'NDA Review Required — Project {project}',
        'Contract amendment: {company} agreement',
        'Compliance training due by {date}',
    ],
    'complaint': [
        'RE: Unresolved issue with {service}',
        'Dissatisfied with recent delivery — need resolution',
        'Escalation: {project} quality concerns',
    ],
    'approval_needed': [
        'Approval required: {project} budget',
        'Sign-off needed: vendor selection for {project}',
        'PO #{number} awaiting your approval',
    ],
    'personal': [
        'Lunch {day}?',
        'Happy birthday!',
        'Weekend plans?',
    ],
}

BODY_TEMPLATES = {
    'meeting_request': "Hi {receiver},\nAre you free {day} afternoon to go over the {project} projections? "
                       "Can we aim for {time}?\n\nThanks,\n{sender}",
    'action_required': "Hi {receiver},\nI need your review on the {project} deliverables by {date}. "
                       "Please check the attached document and provide your feedback.\n\nBest,\n{sender}",
    'fyi': "Hi everyone,\nJust a quick update on {project}. The team has completed phase 2 and we are on track "
           "for the {date} deadline. No action required from your side.\n\nBest,\n{sender}",
    'newsletter': "Dear subscriber,\nHere are this week's highlights in {topic}:\n- New developments in AI\n"
                  "- Market trends update\n- Upcoming events\n\nBest regards,\n{company} Team",
    'spam': "CONGRATULATIONS! You've been selected from millions of users! "
            "Click here to claim your $1,000,000 prize. ACT NOW before this offer expires!",
    'invoice': "Dear {receiver},\nPlease find attached Invoice #{number} for ${amount} due on {date}. "
               "Payment can be made via wire transfer.\n\nRegards,\n{sender}\n{company}",
    'hr': "Hi everyone,\nPlease review the attached document for the updated policy "
          "starting next month. No action required unless you have specific accommodations.\n\nHR Department",
    'legal': "Dear {receiver},\nThe agreement for {project} must be reviewed and signed before {date}. "
             "Please review the attached document carefully.\n\nLegal Team",
    'complaint': "Dear {receiver},\nI am writing to express my dissatisfaction with {service}. "
                 "This is the {ordinal} time I've raised this issue. I expect a resolution within 48 hours.\n\n{sender}",
    'approval_needed': "Hi {receiver},\nI need your approval on the {project} budget (${amount}). "
                       "The vendor needs our PO by {date}. Budget breakdown attached.\n\nBest,\n{sender}",
    'personal': "Hey {receiver}! Just checking in — are you free for lunch on {day}? "
                "There's a new place downtown I've been wanting to try.\n\nCheers,\n{sender}",
}

SENDER_IMPORTANCE_MAP = {
    'ceo':             ('urgent',  0.05),
    'vip':             ('high',    0.10),
    'direct_manager':  ('high',    0.15),
    'colleague':       ('medium',  0.35),
    'external_client': ('medium',  0.15),
    'vendor':          ('low',     0.10),
    'unknown':         ('low',     0.07),
    'spam_likely':     ('low',     0.03),
}

# Category -> whether reply is expected, should archive, needs followup
CATEGORY_BEHAVIOR = {
    'meeting_request':  {'requires_reply': True,  'should_archive': False, 'needs_followup': True,  'followup_days_range': (1, 5)},
    'action_required':  {'requires_reply': True,  'should_archive': False, 'needs_followup': True,  'followup_days_range': (1, 3)},
    'fyi':              {'requires_reply': False, 'should_archive': True,  'needs_followup': False, 'followup_days_range': (0, 0)},
    'newsletter':       {'requires_reply': False, 'should_archive': True,  'needs_followup': False, 'followup_days_range': (0, 0)},
    'spam':             {'requires_reply': False, 'should_archive': True,  'needs_followup': False, 'followup_days_range': (0, 0)},
    'invoice':          {'requires_reply': False, 'should_archive': False, 'needs_followup': True,  'followup_days_range': (3, 14)},
    'hr':               {'requires_reply': False, 'should_archive': True,  'needs_followup': False, 'followup_days_range': (0, 0)},
    'legal':            {'requires_reply': True,  'should_archive': False, 'needs_followup': True,  'followup_days_range': (1, 3)},
    'complaint':        {'requires_reply': True,  'should_archive': False, 'needs_followup': True,  'followup_days_range': (1, 2)},
    'approval_needed':  {'requires_reply': True,  'should_archive': False, 'needs_followup': True,  'followup_days_range': (1, 3)},
    'personal':         {'requires_reply': False, 'should_archive': True,  'needs_followup': False, 'followup_days_range': (0, 0)},
    'other':            {'requires_reply': False, 'should_archive': True,  'needs_followup': False, 'followup_days_range': (0, 0)},
}

# Tone mapping based on sender importance
TONE_MAP = {
    'ceo': 'formal', 'vip': 'formal', 'direct_manager': 'formal',
    'colleague': 'friendly', 'external_client': 'formal',
    'vendor': 'formal', 'unknown': 'formal', 'spam_likely': 'formal',
}

# Adversarial pattern probabilities per task
ADVERSARIAL_RATE = {
    'classify_inbox': 0.20,
    'draft_replies':  0.15,
    'manage_inbox':   0.25,
}


class InboxSimulator:
    """Generates a synthetic inbox with deterministic seeding."""

    def __init__(self, seed: int = 42):
        self.faker = Faker()
        Faker.seed(seed)
        random.seed(seed)

    def generate(self, task_id: str) -> Tuple[List[Email], Dict[str, dict]]:
        """Returns (inbox, ground_truth) for a given task."""
        sizes = {'classify_inbox': 15, 'draft_replies': 25, 'manage_inbox': 40}
        n = sizes.get(task_id, 15)

        inbox = []
        ground_truth = {}

        # Category distribution weighted for each task
        if task_id == 'classify_inbox':
            categories = self._sample_categories_easy(n)
        elif task_id == 'draft_replies':
            categories = self._sample_categories_medium(n)
        else:
            categories = self._sample_categories_hard(n)

        for i in range(n):
            cat = categories[i]
            email, gt = self._generate_email(i, task_id, cat)
            inbox.append(email)
            ground_truth[email.email_id] = gt

        return inbox, ground_truth

    def _sample_categories_easy(self, n: int) -> List[str]:
        cats = ['action_required', 'meeting_request', 'fyi', 'newsletter',
                'spam', 'invoice', 'hr', 'legal', 'complaint',
                'approval_needed', 'personal', 'other']
        return [random.choice(cats) for _ in range(n)]

    def _sample_categories_medium(self, n: int) -> List[str]:
        # Ensure at least 8 reply-required emails
        reply_cats = ['action_required', 'meeting_request', 'complaint',
                      'approval_needed', 'legal']
        archive_cats = ['fyi', 'newsletter', 'spam', 'hr', 'personal']
        result = [random.choice(reply_cats) for _ in range(8)]
        result += [random.choice(archive_cats) for _ in range(n - 8)]
        random.shuffle(result)
        return result

    def _sample_categories_hard(self, n: int) -> List[str]:
        reply_cats = ['action_required', 'meeting_request', 'complaint',
                      'approval_needed', 'legal']
        archive_cats = ['fyi', 'newsletter', 'spam', 'hr', 'personal', 'invoice']
        result = [random.choice(reply_cats) for _ in range(15)]
        result += [random.choice(archive_cats) for _ in range(n - 15)]
        random.shuffle(result)
        return result

    def _generate_email(self, idx: int, task_id: str, category: str) -> Tuple[Email, dict]:
        email_id = f"em_{idx:03d}"

        # Sender
        importance = random.choices(
            list(SENDER_IMPORTANCE_MAP.keys()),
            weights=[v[1] for v in SENDER_IMPORTANCE_MAP.values()]
        )[0]
        sender_name = self.faker.name()
        sender_email = f"{sender_name.lower().replace(' ', '.')}@{self.faker.domain_name()}"
        sender_domain = sender_email.split('@')[1]

        # Priority derived from importance
        base_priority = SENDER_IMPORTANCE_MAP[importance][0]
        priority = self._adjust_priority(base_priority, category)

        # Subject
        subject = self._generate_subject(category)

        # Body
        body = self._generate_body(category, sender_name)

        # Deadline
        deadline = self._maybe_deadline(priority, category)

        # Adversarial twist
        if random.random() < ADVERSARIAL_RATE.get(task_id, 0.15):
            subject, importance, priority = self._apply_adversarial(
                subject, importance, priority, category, idx)

        # Expected tone
        expected_tone = TONE_MAP.get(importance, 'formal')

        # Build reference reply
        ref_reply = self._build_reference_reply(category, sender_name, importance)

        # Has attachment
        has_attachment = category in ('invoice', 'legal', 'approval_needed') or random.random() < 0.15
        attachment_hint = None
        if has_attachment:
            hints = ['Q3_Report.xlsx', 'Contract_v2.pdf', 'Invoice.pdf', 'Budget.xlsx', 'NDA.docx']
            attachment_hint = random.choice(hints)

        # Thread (20% chance for medium/hard)
        thread = None
        if task_id != 'classify_inbox' and random.random() < 0.20:
            thread_msgs = [ThreadMessage(
                sender=self.faker.name(),
                sent_at=datetime.utcnow() - timedelta(hours=random.randint(2, 48)),
                body=f"Previous message regarding {subject[:30]}..."
            )]
            from app.models.observation import EmailThread
            thread = EmailThread(
                thread_id=f"thread_{idx:03d}",
                subject=subject,
                participants=[sender_name, "Alex (You)"],
                messages=thread_msgs,
                message_count=len(thread_msgs)
            )

        email = Email(
            email_id=email_id,
            subject=subject,
            sender=sender_name,
            sender_email=sender_email,
            sender_domain=sender_domain,
            sender_importance=importance,
            body=body,
            received_at=datetime.utcnow() - timedelta(hours=random.randint(0, 72)),
            has_attachment=has_attachment,
            attachment_hint=attachment_hint,
            thread=thread,
            deadline_hint=deadline,
            cc_count=random.randint(0, 5) if category != 'personal' else 0,
        )

        behaviors = CATEGORY_BEHAVIOR.get(category, CATEGORY_BEHAVIOR['other'])
        gt = {
            'priority': priority,
            'category': category,
            'expected_tone': expected_tone,
            'requires_reply': behaviors['requires_reply'],
            'reference_reply': ref_reply,
            'should_archive': behaviors['should_archive'],
            'should_flag': importance in ('ceo', 'vip'),
            'needs_followup': behaviors['needs_followup'],
            'followup_days_range': behaviors['followup_days_range'],
            'deadline_hint': deadline,
        }

        return email, gt

    def _adjust_priority(self, base: str, category: str) -> str:
        if category in ('spam', 'newsletter'):
            return 'low'
        if category in ('legal', 'complaint', 'approval_needed'):
            order = ['low', 'medium', 'high', 'urgent']
            idx = order.index(base) if base in order else 1
            return order[min(idx + 1, 3)]
        return base

    def _generate_subject(self, category: str) -> str:
        templates = SUBJECT_TEMPLATES.get(category, SUBJECT_TEMPLATES.get('fyi'))
        tpl = random.choice(templates)
        return tpl.format(
            project=random.choice(['Atlas', 'Mercury', 'Horizon', 'Q4 Launch', 'Rebrand']),
            day=random.choice(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']),
            date=random.choice(['Friday EOD', 'March 15', 'next Monday', 'end of week']),
            topic=random.choice(['AI strategy', 'budget', 'roadmap', 'hiring', 'security']),
            time=random.choice(['2pm EST', '10am PST', '3pm GMT', '11am ET']),
            company=random.choice(['Acme Corp', 'GlobalTech', 'NexGen', 'CloudFirst']),
            community=random.choice(['Tech Leaders', 'Product Hunt', 'YC']),
            month=random.choice(['January', 'February', 'March', 'April']),
            document=random.choice(['contract', 'proposal', 'budget draft', 'spec']),
            number=str(random.randint(1000, 9999)),
            service=random.choice(['AWS', 'Slack', 'Zoom', 'Figma']),
            ordinal=random.choice(['second', 'third']),
            amount=str(random.randint(5000, 100000)),
        )

    def _generate_body(self, category: str, sender_name: str) -> str:
        tpl = BODY_TEMPLATES.get(category, BODY_TEMPLATES.get('fyi', ''))
        return tpl.format(
            receiver='Alex',
            sender=sender_name,
            project=random.choice(['Atlas', 'Mercury', 'Horizon']),
            day=random.choice(['Monday', 'Tuesday', 'Wednesday']),
            date=random.choice(['Friday EOD', 'March 15', 'end of week']),
            topic=random.choice(['AI', 'budget', 'roadmap']),
            company=random.choice(['Acme Corp', 'GlobalTech']),
            time=random.choice(['2pm EST', '10am PST']),
            number=str(random.randint(1000, 9999)),
            amount=str(random.randint(5000, 100000)),
            service=random.choice(['billing', 'support', 'delivery']),
            ordinal=random.choice(['second', 'third']),
        )

    def _maybe_deadline(self, priority: str, category: str) -> str | None:
        if priority == 'urgent':
            return random.choice(['ASAP', 'within 2 hours', 'by end of day'])
        if priority == 'high' and category in ('action_required', 'legal', 'approval_needed'):
            return random.choice(['by Friday EOD', 'by tomorrow', 'within 24 hours'])
        return None

    def _apply_adversarial(self, subject, importance, priority, category, idx):
        """Apply adversarial pattern to make classification harder."""
        patterns = [
            # Newsletter with urgent-sounding subject
            lambda: ("URGENT UPDATE: " + subject, importance, 'low') if category == 'newsletter' else (subject, importance, priority),
            # VIP sender but it's actually spam
            lambda: (subject, 'vip', priority) if category == 'spam' else (subject, importance, priority),
            # CEO email that's actually just FYI
            lambda: (subject, 'ceo', 'medium') if category == 'fyi' else (subject, importance, priority),
            # Friendly legal email
            lambda: (subject, 'colleague', priority) if category == 'legal' else (subject, importance, priority),
        ]
        return random.choice(patterns)()

    def _build_reference_reply(self, category: str, sender_name: str, importance: str) -> str:
        tone = TONE_MAP.get(importance, 'formal')
        if tone == 'formal':
            greeting = f"Dear {sender_name}"
            closing = "Best regards"
        else:
            greeting = f"Hi {sender_name}"
            closing = "Thanks"

        replies = {
            'meeting_request': f"{greeting},\n\nThank you for reaching out. I am available and will confirm the time shortly. Looking forward to our discussion.\n\n{closing}",
            'action_required': f"{greeting},\n\nThank you for flagging this. I will review the materials and provide my feedback by the requested deadline.\n\n{closing}",
            'complaint': f"{greeting},\n\nI understand your frustration and apologize for the inconvenience. I am escalating this to the relevant team and will ensure you receive a resolution within 24 hours.\n\n{closing}",
            'approval_needed': f"{greeting},\n\nThank you for submitting this for approval. I have reviewed the details and approve the request. Please proceed accordingly.\n\n{closing}",
            'legal': f"{greeting},\n\nI acknowledge receipt of the document. I will review it carefully and provide my signature by the deadline.\n\n{closing}",
            'invoice': f"{greeting},\n\nThank you for sending the invoice. I will process the payment as scheduled.\n\n{closing}",
        }
        return replies.get(category, f"{greeting},\n\nThank you for your email. Noted.\n\n{closing}")
