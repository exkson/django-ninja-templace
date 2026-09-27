"""Logging filters wired in via ``LOGGING`` in settings."""

import logging


class MaxLevelFilter(logging.Filter):
    """Drops records *at or above* ``level``. Pair with a separate ERROR-only
    handler to route errors to a dedicated file without duplication."""

    def __init__(self, level: str = "ERROR") -> None:
        super().__init__()
        self.max_level = logging.getLevelNamesMapping()[level]

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.max_level
