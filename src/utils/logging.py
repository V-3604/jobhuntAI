"""
Logging utilities for the job database system.
"""
import os
import sys
from pathlib import Path

from loguru import logger

from src.utils.config import config


def setup_logging():
    """
    Configure loguru logger for the application.
    
    This sets up console and file logging with rotation.
    """
    # Get logging configuration
    log_config = config["logging"]
    log_level = log_config.get("level", "INFO")
    # Use a default log format string instead of fetching from config
    log_format = "{time} | {level} | {message}"
    log_file = log_config.get("log_file", "logs/jobhunt.log")
    
    # Ensure log directory exists
    log_dir = Path(log_file).parent
    os.makedirs(log_dir, exist_ok=True)
    
    # Remove default handlers
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stderr,
        format=log_format,
        level=log_level,
        colorize=True,
    )
    
    # Add file handler with rotation
    if log_config.get("rotate", True):
        max_size = log_config.get("max_size_mb", 10) * 1024 * 1024  # Convert to bytes
        backup_count = log_config.get("backup_count", 5)
        
        logger.add(
            log_file,
            format=log_format,
            level=log_level,
            rotation=max_size,
            retention=backup_count,
            compression="zip",
        )
    else:
        logger.add(
            log_file,
            format=log_format,
            level=log_level,
        )
    
    logger.info("Logging configured successfully")
    return logger


# Initialize logger on import
setup_logging() 