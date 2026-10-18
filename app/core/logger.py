from datetime import datetime as dt
import datetime
import json
import logging
import logging.config

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
            "DEBUG": "\033[36m",      # Cyan
            "INFO": "\033[32m",       # Green
            "WARNING": "\033[33m",    # Yellow
            "ERROR": "\033[31m",      # Red
            "CRITICAL": "\033[1;31m", # Bold Red
        }

        RESET = "\033[0m"

        def format(self, record):
            original_levelname = record.levelname

            try:
                color = self.COLORS.get(record.levelname, "")
                record.levelname = (
                    f"{color}{record.levelname}{self.RESET}"
                )
                return super().format(record)
            finally:
                record.levelname = original_levelname

# create format that similar to the default of fastapi logger

# logger config

if configEnv.ENV == "production":
    service_logger = logging.getLogger(configEnv.APP_NAME)
    service_handler = logging.StreamHandler()
    service_handler.setFormatter(JSONFormatter())
    service_logger.addHandler(service_handler)
    service_logger.setLevel(logging.INFO)
    service_logger.propagate = False

    http_logger = logging.getLogger("uvicorn.access")
    http_handler = logging.StreamHandler()
    http_handler.setFormatter(JSONFormatter())
    http_logger.addHandler(http_handler)
    http_logger.setLevel(logging.INFO)
    http_logger.propagate = False
else:

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "()": ColorFormatter,
                "format": (
                    "%(asctime)s "
                    "[%(levelname)s] "
                    "%(name)s: %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "()": ColorFormatter,
                "format": "%(asctime)s [HTTP] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "service_console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "http_console": {
                "class": "logging.StreamHandler",
                "formatter": "access",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {
                "handlers": ["service_console"],
                "level": "INFO",
                "propagate": False,
            },
            configEnv.APP_NAME: {
                "handlers": ["service_console"],
                "level": "INFO",
                "propagate": False,
            },
            # Dedicated HTTP Access Logger
            "uvicorn.access": {
                "handlers": ["http_console"],
                "level": "INFO",
                "propagate": False,
            },
            # Uvicorn internal startup/error logs
            "uvicorn.error": {
                "handlers": ["service_console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(LOGGING_CONFIG)

    service_logger = logging.getLogger(configEnv.APP_NAME)
    http_logger = logging.getLogger("uvicorn.access")