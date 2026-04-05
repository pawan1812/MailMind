"""Dynamic Email Injection — PRD §7.4. Urgent emails injected mid-episode in hard task."""

from typing import Optional
from datetime import datetime
from app.models.observation import Email
from app.core.episode import EpisodeState

INJECTION_SCHEDULE = {
    10: 'em_inj_001',
    20: 'em_inj_002',
    30: 'em_inj_003',
    40: 'em_inj_004',
    50: 'em_inj_005',
}

INJECTION_TEMPLATES = {
    'em_inj_001': {
        'subject': '[URGENT] Need Q3 forecast NOW — board meeting in 2h',
        'sender': 'James Richardson', 'sender_email': 'j.richardson@acme-corp.com',
        'sender_domain': 'acme-corp.com', 'sender_importance': 'ceo',
        'body': 'I need the Q3 revenue forecast for the board meeting starting in 2 hours. '
                'Please pull the latest numbers from Finance and send me a summary with the key deltas vs plan. '
                'This is the top priority right now.',
        'deadline_hint': 'within 2 hours',
        'priority': 'urgent', 'category': 'action_required',
        'expected_tone': 'formal', 'requires_reply': True,
    },
    'em_inj_002': {
        'subject': 'LEGAL DEADLINE: NDA signature required by EOD',
        'sender': 'Legal Department', 'sender_email': 'legal@acme-corp.com',
        'sender_domain': 'acme-corp.com', 'sender_importance': 'vip',
        'body': 'The NDA for Project Horizon must be signed before close of business today or the deal stalls. '
                'The document is attached. Please review and confirm you will sign by 5pm.',
        'deadline_hint': 'by end of day',
        'priority': 'urgent', 'category': 'legal',
        'expected_tone': 'formal', 'requires_reply': True,
    },
    'em_inj_003': {
        'subject': 'SYSTEM OUTAGE: Production servers down',
        'sender': 'DevOps Alert', 'sender_email': 'alerts@acme-corp.com',
        'sender_domain': 'acme-corp.com', 'sender_importance': 'direct_manager',
        'body': 'Production servers in US-East region are currently down. '
                'Estimated 500+ customers affected. Engineering team is investigating. '
                'Please acknowledge and escalate to VP Engineering if not resolved in 30 minutes.',
        'deadline_hint': 'ASAP',
        'priority': 'urgent', 'category': 'action_required',
        'expected_tone': 'assertive', 'requires_reply': True,
    },
    'em_inj_004': {
        'subject': 'RE: Unacceptable service quality — escalating',
        'sender': 'Patricia Wong', 'sender_email': 'p.wong@globaltech.io',
        'sender_domain': 'globaltech.io', 'sender_importance': 'vip',
        'body': 'This is my third email about the billing discrepancy. '
                'We were charged $45,000 instead of the agreed $32,000. '
                'If this is not resolved by tomorrow, we will be terminating our contract. '
                'Please have your Finance team investigate immediately.',
        'deadline_hint': 'by tomorrow',
        'priority': 'urgent', 'category': 'complaint',
        'expected_tone': 'formal', 'requires_reply': True,
    },
    'em_inj_005': {
        'subject': 'APPROVAL NEEDED: Marketing budget — 1 hour deadline',
        'sender': 'Sarah Mitchell', 'sender_email': 's.mitchell@acme-corp.com',
        'sender_domain': 'acme-corp.com', 'sender_importance': 'direct_manager',
        'body': 'I need your approval on the Q4 marketing budget ($180K) within the next hour. '
                'The vendor needs our PO by 3pm or we lose the campaign slot. '
                'Budget breakdown attached. Please reply with APPROVED or your concerns.',
        'deadline_hint': 'within 1 hour',
        'priority': 'urgent', 'category': 'approval_needed',
        'expected_tone': 'formal', 'requires_reply': True,
    },
}


class DynamicInjector:
    """Injects urgent emails at specific steps during the hard task."""

    def check_and_inject(self, episode: EpisodeState) -> Optional[Email]:
        if episode.task_id != 'manage_inbox':
            return None
        if episode.step not in INJECTION_SCHEDULE:
            return None

        inj_id = INJECTION_SCHEDULE[episode.step]
        if inj_id in episode.injected_emails:
            return None

        tpl = INJECTION_TEMPLATES[inj_id]
        injected = Email(
            email_id=inj_id,
            subject=tpl['subject'],
            sender=tpl['sender'],
            sender_email=tpl['sender_email'],
            sender_domain=tpl['sender_domain'],
            sender_importance=tpl['sender_importance'],
            body=tpl['body'],
            received_at=datetime.utcnow(),
            deadline_hint=tpl.get('deadline_hint'),
            injected=True,
        )

        # Prepend to inbox right after current position
        insert_pos = min(episode.current_idx + 1, len(episode.inbox))
        episode.inbox.insert(insert_pos, injected)
        episode.injected_emails.add(inj_id)

        # Add ground truth
        episode.ground_truth[inj_id] = {
            'priority': tpl['priority'],
            'category': tpl['category'],
            'expected_tone': tpl.get('expected_tone', 'formal'),
            'requires_reply': tpl.get('requires_reply', True),
            'reference_reply': f"Thank you for flagging this. I will handle it immediately.",
            'should_archive': False,
            'needs_followup': True,
            'followup_days_range': (1, 3),
        }

        return injected
