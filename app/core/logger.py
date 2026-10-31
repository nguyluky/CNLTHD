import copy
from datetime import datetime as dt
import datetime
import json
import logging
from logging.handlers import (
    QueueHandler,
    QueueListener,
    RotatingFileHandler,
)
import queue
import sys
import threading

from app.core.config import configEnv

log_queue = queue.SimpleQueue()

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        log_obj = {
            "time_stamp": dt.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": getattr(record, "module", None),
            "func_name": getattr(record, "funcName", None),
        }

        if record.exc_text:
            log_obj["exception"] = record.exc_text
        elif record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_obj["stack_info"] = self.formatStack(record.stack_info)

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

        def format(self, record: logging.LogRecord):
            original_levelname = record.levelname

            try:
                color = self.COLORS.get(record.levelname, "")
                record.levelname = (
                    f"{color}{record.levelname}{self.RESET}"
                )
                return super().format(record)
            finally:
                record.levelname = original_levelname

# # create format that similar to the default of fastapi logger
# # logger config

# if configEnv.ENV == "production":
#     json_formatter = JSONFormatter()
    
#     # Console handler
#     stream_handler = logging.StreamHandler()
#     stream_handler.setFormatter(json_formatter)
    
#     # File handler (Max 10MB per file, keeps last 5 backup files)
#     # Actual output handlers.
#     file_handler = RotatingFileHandler(
#         "app.log",
#         maxBytes=10 * 1024 * 1024,
#         backupCount=5,
#         encoding="utf-8",
#     )
#     file_handler.setFormatter(json_formatter)

#     console_handler = logging.StreamHandler()
#     console_handler.setFormatter(JSONFormatter())

#     # Queue handler: attached to application loggers.
#     queue_handler = QueueHandler(log_queue)

#     # Background listener: performs actual logging I/O.
#     log_listener = QueueListener(
#         log_queue,
#         file_handler,
#         console_handler,
#         respect_handler_level=True,
#     )

#     log_listener.start()

#     service_logger = logging.getLogger(configEnv.APP_NAME)
#     service_logger.handlers.clear()
#     service_logger.addHandler(queue_handler)
#     service_logger.setLevel(logging.INFO)
#     service_logger.propagate = False

#     http_logger = logging.getLogger("app.access")
#     http_logger.handlers.clear()
#     http_logger.addHandler(queue_handler)
#     http_logger.setLevel(logging.INFO)
#     http_logger.propagate = False
# else:

#     LOGGING_CONFIG = {
#         "version": 1,
#         "disable_existing_loggers": False,
#         "formatters": {
#             "standard": {
#                 "()": ColorFormatter,
#                 "format": (
#                     "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
#                 ),
#                 "datefmt": "%Y-%m-%d %H:%M:%S",
#             },
#             "file_formatter": {
#                 "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#                 "datefmt": "%Y-%m-%d %H:%M:%S",
#             },
#         },
#         "handlers": {
#             "standard_console": {
#                 "class": "logging.StreamHandler",
#                 "formatter": "standard",
#                 "stream": "ext://sys.stdout",
#             },
#             "file": {
#                 "class": "logging.handlers.RotatingFileHandler",
#                 "filename": "app.log",
#                 "maxBytes": 10 * 1024 * 1024,
#                 "backupCount": 3,
#                 "formatter": "file_formatter",
#                 "encoding": "utf-8",
#             },
#         },
#         "loggers": {
#             "": {
#                 "handlers": ["standard_console", "file"],
#                 "level": "INFO",
#                 "propagate": False,
#             },
#             configEnv.APP_NAME: {
#                 "handlers": ["standard_console", "file"],
#                 "level": "INFO",
#                 "propagate": False,
#             },
#             "app.access": {
#                 "handlers": ["standard_console", "file"],
#                 "level": "INFO",
#                 "propagate": False,
#             },
#             "uvicorn.error": {
#                 "handlers": ["standard_console", "file"],
#                 "level": "INFO",
#                 "propagate": False,
#             },
#         },
#     }

#     logging.config.dictConfig(LOGGING_CONFIG)

#     service_logger = logging.getLogger(configEnv.APP_NAME)

class SafeQueueHandler(QueueHandler):
    """
    Prepare the LogRecord before passing it to QueueListener.

    - Resolve message arguments in the calling thread.
    - Preserve exception information as formatted text.
    - Perform actual output formatting and I/O in the listener thread.
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        prepared = copy.copy(record)

        # Resolve the message before the original arguments can change.
        message = record.getMessage()

        prepared.msg = message
        prepared.message = message
        prepared.args = None

        # QueueHandler's default prepare() clears exc_info.
        # Preserve the traceback as text so JSONFormatter can put it in a separate "exception" field.
        if record.exc_info:
            prepared.exc_text = logging.Formatter().formatException(
                record.exc_info
            )
            prepared.exc_info = None

        return prepared

# One listener per application process.
_log_queue = queue.SimpleQueue()

_log_listener: QueueListener | None = None
_queue_handler: SafeQueueHandler | None = None
_output_handlers: list[logging.Handler] = []

_logging_lock = threading.Lock()

def configure_logging() -> None:
    """
    Configure all application loggers to use one QueueHandler.

    Call once during application startup.
    Safe to call more than once in the same process.
    """

    global _log_listener
    global _queue_handler
    global _output_handlers

    with _logging_lock:
        if _log_listener is not None:
            return

        is_production = configEnv.ENV == "production"

        # Choose output formatters
        if is_production:
            console_formatter = JSONFormatter()
            file_formatter = JSONFormatter()
            backup_count = 5
        else:
            console_formatter = ColorFormatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            backup_count = 3

        # Create real output handlers
        # These are used only by QueueListener.
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)

        file_handler = RotatingFileHandler(
            "app.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(file_formatter)

        _output_handlers = [
            console_handler,
            file_handler,
        ]

        # Create one QueueHandler and QueueListener
        _queue_handler = SafeQueueHandler(_log_queue)
        _queue_handler.setLevel(logging.INFO)

        _log_listener = QueueListener(
            _log_queue,
            *_output_handlers,
            respect_handler_level=True,
        )

        # Start listener before attaching QueueHandler.
        _log_listener.start()

        # Configure root logger
        root_logger = logging.getLogger()

        root_logger.handlers.clear()
        root_logger.addHandler(_queue_handler)
        root_logger.setLevel(logging.INFO)

        # Configure application and Uvicorn loggers
        managed_logger_names = {
            configEnv.APP_NAME,
            "app.access",
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
        }

        for logger_name in managed_logger_names:
            logger = logging.getLogger(logger_name)

            logger.handlers.clear()
            logger.addHandler(_queue_handler)
            logger.setLevel(logging.INFO)

            # Prevent a record from being handled again by root.
            logger.propagate = False


def shutdown_logging() -> None:
    """
    Stop the listener and close output handlers.

    QueueListener.stop() inserts a sentinel into the queue and
    waits for the listener thread to finish processing earlier records.
    """

    global _log_listener
    global _queue_handler
    global _output_handlers

    with _logging_lock:
        if _log_listener is None:
            return

        listener = _log_listener
        handlers = list(_output_handlers)

        # Stop listener first. It processes queued records before exit.
        listener.stop()

        # Flush and close the real output handlers.
        for handler in handlers:
            handler.flush()
            handler.close()

        _log_listener = None
        _queue_handler = None
        _output_handlers = []


service_logger = logging.getLogger(configEnv.APP_NAME)
http_logger = logging.getLogger("app.access")