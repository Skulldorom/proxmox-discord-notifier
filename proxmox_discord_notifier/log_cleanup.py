"""Log cleanup utilities for managing log file retention."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Cleanup runs every 24 hours (in seconds)
CLEANUP_INTERVAL_SECONDS = 86400


async def cleanup_old_logs() -> int:
    """
    Delete log files older than the configured retention period.
    
    Returns:
        Number of log files deleted
    """
    # If retention is set to 0, never delete logs
    if settings.log_retention_days == 0:
        logger.debug("Log retention disabled (set to 0), skipping cleanup")
        return 0
    
    log_dir = settings.log_directory
    if not log_dir.exists():
        logger.warning(f"Log directory does not exist: {log_dir}")
        return 0
    
    cutoff_time = datetime.now() - timedelta(days=settings.log_retention_days)
    deleted_count = 0
    
    try:
        for log_file in log_dir.glob("*.log"):
            if not log_file.is_file():
                continue
            
            # Get file modification time
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            if mtime < cutoff_time:
                try:
                    log_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old log file: {log_file.name}")
                except OSError as e:
                    logger.error(f"Failed to delete log file {log_file.name}: {e}")
    
    except Exception as e:
        logger.error(f"Error during log cleanup: {e}")
    
    if deleted_count > 0:
        logger.info(f"Cleanup completed: deleted {deleted_count} old log file(s)")
    
    return deleted_count


async def periodic_cleanup_task():
    """
    Periodically run log cleanup. Runs every 24 hours.
    """
    while True:
        try:
            deleted = await cleanup_old_logs()
            logger.debug(f"Periodic cleanup executed, deleted {deleted} file(s)")
        except Exception as e:
            logger.error(f"Error in periodic cleanup task: {e}")
        
        # Wait before next cleanup
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
