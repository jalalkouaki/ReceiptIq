import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from config import load_settings

_logger = None


def setup_logger(logs_dir=None):
    global _logger
    if _logger is not None and not logs_dir:
        return _logger

    if not logs_dir:
        cfg = load_settings()
        logs_dir = cfg.get("LOGS_DIR")

    os.makedirs(logs_dir, exist_ok=True)
    log_path = Path(logs_dir) / "receiptiq.log"

    logger = logging.getLogger("receiptiq")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    
    # Custom format: timestamp - level - event_type - user - message
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Console handler for debugging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _logger = logger
    return _logger


def log_event(event_type: str, message: str, level="INFO", user: str = "system"):
    logger = setup_logger()
    formatted_msg = f"event={event_type} user={user} :: {message}"
    if level.upper() == "DEBUG":
        logger.debug(formatted_msg)
    elif level.upper() == "WARNING":
        logger.warning(formatted_msg)
    elif level.upper() == "ERROR":
        logger.error(formatted_msg)
    elif level.upper() == "CRITICAL":
        logger.critical(formatted_msg)
    else:
        logger.info(formatted_msg)
