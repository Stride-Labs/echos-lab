import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Initialize logger once at module level
logger = logging.getLogger("echos")

# Skip if logger is already configured
if not logger.hasHandlers():
    # Set format and level
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(log_dir / "echos.log", maxBytes=10 * 1024 * 1024, backupCount=5)  # 10MB
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to parent loggers (to prevent duplicate logs)
    logger.propagate = False
