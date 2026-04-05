"""MailMind OpenEnv — Main application factory. PRD §13.1."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan handler — replaces deprecated on_event."""
    # Startup
    try:
        from app.db.firebase_client import get_firestore_client
        client = get_firestore_client()
        if client:
            print("Firebase Firestore connected")
        else:
            print("Firebase not configured -- using in-memory storage")
    except Exception:
        print("Firebase not available -- using in-memory storage")

    print(f"MailMind OpenEnv v{settings.app_version} started on port {settings.port}")
    yield
    # Shutdown
    print("MailMind shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title='MailMind OpenEnv',
        description='Email Triage & Response AI Agent — OpenEnv Reinforcement Learning Environment. '
                     '3 tasks (easy/medium/hard), 8 action types, dense reward, deterministic graders.',
        version=settings.app_version,
        docs_url='/docs',
        redoc_url='/redoc',
        lifespan=lifespan,
    )

    # CORS (required for HF Spaces iframe)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_methods=['*'],
        allow_headers=['*'],
    )

    # Import & register routes
    from app.routes import env_routes, task_routes, grader_routes
    from app.routes import baseline_routes, health_routes

    app.include_router(env_routes.router)
    app.include_router(task_routes.router)
    app.include_router(grader_routes.router)
    app.include_router(baseline_routes.router)
    app.include_router(health_routes.router)

    # Root redirect → Swagger UI (HuggingFace opens / by default)
    @app.get('/', include_in_schema=False)
    def root():
        return RedirectResponse(url='/docs')

    # Serve openenv.yaml
    @app.get('/openenv.yaml', include_in_schema=False)
    def serve_openenv():
        import os
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'openenv.yaml')
        return FileResponse(yaml_path, media_type='text/yaml')

    return app

app = create_app()
