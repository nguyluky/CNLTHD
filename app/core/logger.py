from datetime import datetime as dt
import datetime
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "time_stamp": dt.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName 
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


#logger config
logger = logging.getLogger("app_logger")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)