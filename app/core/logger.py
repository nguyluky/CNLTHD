from datetime import datetime as dt
import datetime
import json
import logging
import logging.config
from logging.handlers import RotatingFileHandler

from app.core.config import configEnv


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "time_stamp": dt.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": getattr(record, "module", None),
            "func_name": getattr(record, "funcName", None),
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }

    RESET = "\033[0m"

    def format(self, record):
        original_levelname = record.levelname

        try:
            color = self.COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname}{self.RESET}"
            return super().format(record)
        finally:
            record.levelname = original_levelname


# create format that similar to the default of fastapi logger
# logger config

if configEnv.ENV == "production":
    json_formatter = JSONFormatter()

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(json_formatter)

    # File handler (Max 10MB per file, keeps last 5 backup files)
    file_handler = RotatingFileHandler(
        "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(json_formatter)

    service_logger = logging.getLogger(configEnv.APP_NAME)
    service_logger.addHandler(stream_handler)
    service_logger.addHandler(file_handler)
    service_logger.setLevel(logging.INFO)
    service_logger.propagate = False

    http_logger = logging.getLogger("app.access")
    http_logger.addHandler(stream_handler)
    http_logger.addHandler(file_handler)
    http_logger.setLevel(logging.INFO)
    http_logger.propagate = False
else:
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "()": ColorFormatter,
                "format": ("%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "file_formatter": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "standard_console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "app.log",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 3,
                "formatter": "file_formatter",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {
                "handlers": ["standard_console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            configEnv.APP_NAME: {
                "handlers": ["standard_console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "app.access": {
                "handlers": ["standard_console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["standard_console", "file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(LOGGING_CONFIG)

    service_logger = logging.getLogger(configEnv.APP_NAME)
