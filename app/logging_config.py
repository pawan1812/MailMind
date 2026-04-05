"""Structured logging configuration — PRD §2.3 (structlog + rich)."""

import logging
import sys
from typing import Optional

try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False

try:
    from rich.logging import RichHandler
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False


def setup_logging(level: str = "info", json_format: bool = False) -> logging.Logger:
    """Configure structured logging for MailMind.

    Uses structlog+rich when available, falls back to stdlib logging.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if _HAS_STRUCTLOG:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        if json_format:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer(colors=True))

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        return structlog.get_logger("mailmind")

    # Fallback: stdlib logging with optional rich
    handlers = []
    if _HAS_RICH:
        handlers.append(RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
        ))
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        ))
        handlers.append(handler)

    logger = logging.getLogger("mailmind")
    logger.setLevel(log_level)
    logger.handlers = handlers
    return logger


# Singleton logger
logger = setup_logging()
