from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.config import settings


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.log_level.upper())
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(
            JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"levelname": "level", "asctime": "timestamp"},
            )
        )
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root.addHandler(handler)
