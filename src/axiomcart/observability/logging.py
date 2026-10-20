"""Structured logging with secret redaction and correlation IDs."""
import logging
import sys
from typing import Any, Dict
import structlog

SENSITIVE_KEYS = {
    "access_token",
    "token",
    "client_secret",
    "secret",
    "password",
    "authorization",
    "api_key",
    "salesforce_client_secret",
}


def redact_sensitive_data(
    logger: logging.Logger,
    method_name: str,
    event_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Redacts known sensitive keys in log event dictionaries."""
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging using structlog."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_sensitive_data,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "axiomcart") -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
