import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Use a flag for development mode; later replace with your config
is_development = True

def setup_logging() -> None:
    log_dir = Path("./logs/telegram-bot")  # Keep bot logs separate
    log_dir.mkdir(parents=True, exist_ok=True)

    rotation_size = 10 * 1024 * 1024
    backup_count = 5

    root_logger = logging.getLogger()
    base_level = logging.INFO if is_development else logging.WARNING
    root_logger.setLevel(base_level)

    # Remove old handlers if any
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(base_level)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=rotation_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(base_level)
    root_logger.addHandler(file_handler)

    error_file_handler = RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=rotation_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_file_handler)

    # Optional: if you want **all** pymongo logs visible, comment these lines out:
    # logging.getLogger("watchfiles").setLevel(logging.ERROR)
    # for logger_name in [
    #     "pymongo", "pymongo.connection", "pymongo.command", 
    #     "pymongo.serverSelection", "pymongo.topology"
    # ]:
    #     logging.getLogger(logger_name).setLevel(logging.WARNING)

    logging.info(f"Application initialized in {'development' if is_development else 'production'} mode")

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)