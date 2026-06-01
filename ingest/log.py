"""
Logging setup — pretty console for local dev, structured JSON for K8s.

Format is selected in this order:
1. ``LOG_FORMAT`` env var: ``console`` → pretty, ``json`` → JSON.
2. Auto-detect: if stdout is a TTY → pretty; otherwise → JSON.

This means ``poetry run python run.py`` in a terminal gets pretty output
by default.  In K8s / Docker / CI (no TTY, or ``LOG_FORMAT=json``), every
line is a valid JSON object ready for log aggregators (Datadog, Loki, ELK…).

Override log verbosity with ``LOG_LEVEL`` (default ``INFO``).

Usage::

    from ingest.log import get_logger
    log = get_logger(__name__)

    log.info("batch_upserted", collection="products", upserted=42, modified=3)
    log.warning("menu_step_unresolved", product_id=31, name="Plateau entre amis")
    log.error("mongo_error", error=str(exc))
"""

import logging
import os
import sys

import structlog

_CONFIGURED = False


def _use_json() -> bool:
    """Decide whether to emit JSON or pretty console output.

    Priority: LOG_FORMAT env var → TTY auto-detect.
    """
    fmt = os.getenv("LOG_FORMAT", "").lower().strip()
    if fmt == "json":
        return True
    if fmt == "console":
        return False
    # Auto-detect: no TTY = K8s / CI / Docker → JSON
    return not sys.stdout.isatty()


def configure_logging() -> None:
    """Configure structlog once for the entire process.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if _use_json():
        # ── K8s / CI / Docker: newline-delimited JSON ────────────────────────
        # Each line is a valid JSON object — easy to ingest with any aggregator.
        # Stack traces are serialised under the "exception" key.
        processors.append(structlog.processors.format_exc_info)
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        # ── Local dev / Python terminal: coloured, human-readable ────────────
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog so pymongo warnings appear too.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    _CONFIGURED = True


def get_logger(name: str = __name__):
    """Return a bound structlog logger with the module name pre-bound.

    The ``logger`` key appears in every log line — useful for filtering
    in K8s log aggregators (e.g. ``{logger: "ingest.transform"}``).

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A structlog ``BoundLogger`` with ``logger=name`` pre-bound.
    """
    configure_logging()
    return structlog.get_logger().bind(logger=name)
