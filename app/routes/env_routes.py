"""Environment routes — POST /reset, POST /step, GET /state. PRD §13."""

from fastapi import APIRouter, HTTPException, Header, Response
from typing import Optional
from pydantic import BaseModel

from app.models.action import Action
from app.dependencies import get_env

router = APIRouter(tags=['environment'])


class ResetRequest(BaseModel):
    task_id: str = 'classify_inbox'
    seed: Optional[int] = None


@router.post('/reset')
def reset_env(req: ResetRequest, response: Response,
              x_session_id: Optional[str] = Header(default='default')):
    """Start a new episode."""
    try:
        env = get_env(x_session_id)
        obs = env.reset(task_id=req.task_id, seed=req.seed)
        response.headers['X-Session-ID'] = x_session_id
        response.headers['X-Episode-ID'] = obs.episode_id
        return obs.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class StepRequest(BaseModel):
    action: Action


@router.post('/step')
def step_env(req: StepRequest,
             x_session_id: Optional[str] = Header(default='default')):
    """Submit one action."""
    env = get_env(x_session_id)
    if env.episode is None:
        raise HTTPException(status_code=400, detail='No active episode. Call /reset first.')

    try:
        result = env.step(req.action)
        return result.model_dump()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/state')
def get_state(x_session_id: Optional[str] = Header(default='default')):
    """Get current episode state."""
    env = get_env(x_session_id)
    return env.state()
