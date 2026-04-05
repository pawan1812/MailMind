"""Health routes — GET /health. PRD §13."""

from fastapi import APIRouter
from datetime import datetime, timezone
from app.config import settings
from app.db.firebase_client import is_firebase_available

router = APIRouter(tags=['health'])

_started_at = datetime.now(timezone.utc)


@router.get('/health')
def health_check():
    """Health check endpoint."""
    uptime = (datetime.now(timezone.utc) - _started_at).total_seconds()
    return {
        'status': 'healthy',
        'version': settings.app_version,
        'uptime_seconds': round(uptime, 1),
        'firebase': 'connected' if is_firebase_available() else 'not_configured (using in-memory)',
    }
