"""Logging configuration for Truth Engine."""

from __future__ import annotations

import logging
import sys

# ANSI colors for terminal readability
COLORS = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "BLUE": "\033[34m",
    "MAGENTA": "\033[35m",
    "CYAN": "\033[36m",
    "RED": "\033[31m",
    "WHITE": "\033[37m",
}


class ColorFormatter(logging.Formatter):
    """Colored log formatter for terminal output."""

    LEVEL_COLORS = {
        logging.DEBUG: COLORS["DIM"],
        logging.INFO: COLORS["CYAN"],
        logging.WARNING: COLORS["YELLOW"],
        logging.ERROR: COLORS["RED"],
        logging.CRITICAL: COLORS["RED"] + COLORS["BOLD"],
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, COLORS["RESET"])
        reset = COLORS["RESET"]
        dim = COLORS["DIM"]

        # Short module name
        module = record.name.split(".")[-1] if record.name else "root"

        timestamp = self.formatTime(record, "%H:%M:%S")
        level = record.levelname[0]  # Single letter: I, W, E, D

        msg = record.getMessage()

        return f"{dim}{timestamp}{reset} {color}{level}{reset} {COLORS['MAGENTA']}{module:>20}{reset}  {msg}"


def setup_logging(level: str = "DEBUG") -> None:
    """Configure colored, readable logging for the Truth Engine."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorFormatter())
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
