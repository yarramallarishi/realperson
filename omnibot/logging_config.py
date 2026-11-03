import json
import logging
import logging.config
from datetime import datetime, timezone

from omnibot.config import get_settings


class StructuredFormatter(logging.Formatter):
    _reserved = set(logging.makeLogRecord({}).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update({
            key: value for key, value in record.__dict__.items()
            if key not in self._reserved and key not in {"message", "asctime"}
        })
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    level = get_settings().log_level.upper()
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"structured": {"()": StructuredFormatter}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "structured"}},
        "root": {"handlers": ["console"], "level": level},
    })
