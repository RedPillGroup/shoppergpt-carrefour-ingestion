"""
Logging setup — structured JSON for K8s / pretty console for local dev.

The renderer is chosen automatically:
- **TTY detected** (local terminal) → coloured, human-readable ``ConsoleRenderer``.
- **No TTY** (K8s, CI, Docker) → newline-delimited JSON, one object per line,
  ready for log aggregators (Datadog, Loki, ELK, GCP Logging…).

Override with the ``LOG_LEVEL`` env var (default ``INFO``).

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


def configure_logging() -> None:
    """Configure structlog once for the entire process.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    is_tty = sys.stdout.isatty()

    # Processors run for every log entry, in order
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if is_tty:
        # ── Local dev: coloured, human-readable ──────────────────────────────
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # ── K8s / CI / Docker: newline-delimited JSON ────────────────────────
        # Each log line is a valid JSON object — easy to ingest with any
        # log aggregator.  Stack traces are serialised under "exception" key.
        processors.append(structlog.processors.format_exc_info)
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also route stdlib ``logging`` through structlog so pymongo / tqdm
    # warnings land in the same structured stream.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    _CONFIGURED = True


def get_logger(name: str = __name__):
    """Return a bound structlog logger with the module name pre-bound.

    The ``logger`` key is bound at creation time so it appears in every
    log line emitted by this logger — useful for filtering in K8s log
    aggregators (e.g. ``{logger: "ingest.transform"}``).

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A structlog ``BoundLogger`` with ``logger=name`` pre-bound.
    """
    configure_logging()
    return structlog.get_logger().bind(logger=name)
