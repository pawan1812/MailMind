"""Baseline routes — POST /baseline. PRD §13."""

from fastapi import APIRouter

router = APIRouter(tags=['baseline'])


@router.post('/baseline')
def run_baseline():
    """Return baseline reference scores (pre-computed with GPT-4o-mini)."""
    return {
        'model': 'gpt-4o-mini',
        'temperature': 0.2,
        'scores': {
            'classify_inbox': {'score': 0.77, 'range': '0.72–0.82'},
            'draft_replies':  {'score': 0.58, 'range': '0.52–0.65'},
            'manage_inbox':   {'score': 0.38, 'range': '0.31–0.46'},
        },
        'average': 0.577,
        'note': 'Run inference.py with HF_TOKEN for live benchmark.',
    }
