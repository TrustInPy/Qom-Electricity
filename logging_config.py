import logging
import logging.handlers
import os
from config import LOG_DIR, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, "bot.log")

    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL.upper())

    ch = logging.StreamHandler()
    ch.setLevel(LOG_LEVEL.upper())
    ch.setFormatter(fmt)
    root.addHandler(ch)

    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    fh.setLevel(LOG_LEVEL.upper())
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logging.getLogger(__name__).info("Logging initialized -> %s", log_path)
