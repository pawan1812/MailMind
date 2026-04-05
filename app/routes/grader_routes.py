"""Grader routes — POST /grader. PRD §13.6."""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from app.dependencies import get_env

router = APIRouter(tags=['grader'])


@router.post('/grader')
def run_grader(x_session_id: Optional[str] = Header(default='default')):
    """Grade the current episode. Call after episode is done."""
    env = get_env(x_session_id)
    if env.episode is None:
        raise HTTPException(status_code=400, detail='No episode to grade. Call /reset first.')

    try:
        result = env.grade()
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
