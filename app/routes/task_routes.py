"""Task routes — GET /tasks. PRD §13.5."""

from fastapi import APIRouter

router = APIRouter(tags=['tasks'])


TASKS_META = [
    {
        'id': 'classify_inbox',
        'name': 'Email Classification',
        'difficulty': 'easy',
        'max_steps': 20,
        'inbox_size': 15,
        'description': 'Classify all inbox emails by priority and category.',
        'action_types': ['classify_email', 'archive', 'delete', 'skip'],
        'grader': 'ClassificationGrader',
        'score_range': [0.0, 1.0],
    },
    {
        'id': 'draft_replies',
        'name': 'Reply Drafting',
        'difficulty': 'medium',
        'max_steps': 30,
        'inbox_size': 25,
        'description': 'Classify emails and draft contextually appropriate replies with correct tone.',
        'action_types': ['classify_email', 'draft_reply', 'send_reply', 'archive', 'skip'],
        'grader': 'ClassificationGrader (40%) + ReplyGrader (60%)',
        'score_range': [0.0, 1.0],
    },
    {
        'id': 'manage_inbox',
        'name': 'Full Inbox Management',
        'difficulty': 'hard',
        'max_steps': 60,
        'inbox_size': 40,
        'description': 'Complete inbox lifecycle: classify, reply, archive, flag, schedule follow-ups, '
                       'and handle 5 dynamic urgent email injections.',
        'action_types': ['classify_email', 'draft_reply', 'send_reply', 'archive',
                         'delete', 'flag', 'schedule_followup', 'skip'],
        'grader': 'WorkflowGrader (5-component weighted composite)',
        'score_range': [0.0, 1.0],
    },
]


@router.get('/tasks')
def list_tasks():
    """List all available tasks with metadata."""
    return TASKS_META
