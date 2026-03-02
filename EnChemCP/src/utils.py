import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Project Root Directory
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
LOG_DIR = PROJECT_ROOT / "logs"

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Load Environment Variables
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    # 모듈 최초 로드 시점이므로 logger 미생성 — logging 모듈 직접 사용
    logging.warning(
        ".env file not found at %s. Proceeding with system environment variables.",
        ENV_PATH,
    )


def setup_logger(name: str) -> logging.Logger:
    """
    Sets up a logger with both console and file handlers.
    Log files are separated by day (e.g., app_2026-02-24.log) and
    error logs are kept in a separate file (error_2026-02-24.log).

    Args:
        name (str): The name of the logger (usually __name__).

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Standard formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Avoid duplicate handlers if logger is already configured
    if not logger.handlers:
        logger.addHandler(console_handler)

        # 2. General File Handler (INFO and above)
        general_log_path = LOG_DIR / f"app_{today_str}.log"
        file_handler = logging.FileHandler(general_log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 3. Error File Handler (ERROR and above)
        error_log_path = LOG_DIR / f"error_{today_str}.log"
        error_file_handler = logging.FileHandler(error_log_path, encoding='utf-8')
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(formatter)
        logger.addHandler(error_file_handler)

    return logger

def get_config(key: str, default_value: str = "") -> str:
    """
    Retrieves a configuration value from environment variables.

    Args:
        key (str): The environment variable key.
        default_value (str): The default value if the key is not found.

    Returns:
        str: The configuration value.
    """
    return os.getenv(key, default_value)
