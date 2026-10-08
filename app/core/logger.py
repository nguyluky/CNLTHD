from datetime import datetime as dt
import datetime
import json
import logging
import logging.config

from app.core.config import config


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "time_stamp": dt.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName,
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


# create format that similar to the default of fastapi logger

# logger config

if config.ENV == "production":
    logger = logging.getLogger(config.APP_NAME)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
else:
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
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": "INFO",
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(LOGGING_CONFIG)

    logger = logging.getLogger(config.APP_NAME)