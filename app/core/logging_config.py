"""
Logging configuration for ColdEdge Email Service
Provides structured logging for production environments
"""

import logging
import logging.config
import os
from pathlib import Path
from typing import Dict, Any

# Get log level from environment variable
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Ensure logs directory exists
BASE_DIR = Path(__file__).parent.parent.parent  # emailtracker directory
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Define log file paths
LOG_FILE = LOGS_DIR / "emailtracker.log"
ERROR_LOG_FILE = LOGS_DIR / "emailtracker_errors.log"

# Logging configuration
LOGGING_CONFIG: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "detailed",
            "filename": str(LOG_FILE),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": str(ERROR_LOG_FILE),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "loggers": {
        "app": {
            "level": LOG_LEVEL,
            "handlers": ["console", "file", "error_file"],
            "propagate": False
        },
        "app.api": {
            "level": LOG_LEVEL,
            "handlers": ["console", "file"],
            "propagate": False
        },
        "app.core": {
            "level": LOG_LEVEL,
            "handlers": ["console", "file", "error_file"],
            "propagate": False
        },
        "app.services": {
            "level": LOG_LEVEL,
            "handlers": ["console", "file"],
            "propagate": False
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        }
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"]
    }
}

def setup_logging():
    """Configure logging for the application"""
    try:
        # Ensure log files can be created
        LOG_FILE.touch(exist_ok=True)
        ERROR_LOG_FILE.touch(exist_ok=True)
        
        logging.config.dictConfig(LOGGING_CONFIG)
        
        # Get logger for this module
        logger = logging.getLogger("app.logging")
        logger.info(f"Logging configured with level: {LOG_LEVEL}")
        logger.info(f"Log files: {LOG_FILE}, {ERROR_LOG_FILE}")
        
        return logger
    except Exception as e:
        # Fallback to basic console logging if file logging fails
        logging.basicConfig(
            level=LOG_LEVEL,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger = logging.getLogger("app.logging")
        logger.warning(f"Failed to configure file logging: {e}")
        logger.info("Using basic console logging as fallback")
        return logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(f"app.{name}")
