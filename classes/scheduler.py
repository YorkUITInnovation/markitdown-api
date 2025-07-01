import asyncio
import schedule
import threading
import time
from datetime import datetime
from typing import Optional
from classes.config import IMAGE_CLEANUP_DAYS, IMAGE_CLEANUP_TIME
from classes.image_extractor import ImageExtractor
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageCleanupScheduler:
    """Scheduler for running image cleanup tasks"""

    def __init__(self, image_extractor: ImageExtractor):
        self.image_extractor = image_extractor
        self.cleanup_days = IMAGE_CLEANUP_DAYS
        self.cleanup_time = IMAGE_CLEANUP_TIME
        self.scheduler_thread: Optional[threading.Thread] = None
        self.running = False

    def run_cleanup(self):
        """Execute the image cleanup task"""
        try:
            logger.info(f"Starting image cleanup task (deleting folders older than {self.cleanup_days} days)")
            result = self.image_extractor.cleanup_old_images(self.cleanup_days)

            if result["status"] == "completed":
                logger.info(f"Cleanup completed successfully:")
                logger.info(f"  - Deleted folders: {result['deleted_folders']}")
                logger.info(f"  - Freed space: {result['freed_space_mb']} MB")
                if result['deleted_folder_names']:
                    logger.info(f"  - Deleted folder names: {', '.join(result['deleted_folder_names'])}")
            elif result["status"] == "skipped":
                logger.info(f"Cleanup skipped: {result['reason']}")
            else:
                logger.error(f"Cleanup failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Error during scheduled cleanup: {e}")

    def start_scheduler(self):
        """Start the background scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        # Validate cleanup time format
        try:
            time_parts = self.cleanup_time.split(':')
            if len(time_parts) != 2:
                raise ValueError("Time format must be HH:MM")
            hour, minute = int(time_parts[0]), int(time_parts[1])
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError("Invalid time values")
        except ValueError as e:
            logger.error(f"Invalid cleanup time format '{self.cleanup_time}': {e}")
            logger.error("Using default time 02:00")
            self.cleanup_time = "02:00"

        # Schedule the cleanup task
        schedule.every().day.at(self.cleanup_time).do(self.run_cleanup)

        self.running = True

        # Start the scheduler in a separate thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

        logger.info(f"Image cleanup scheduler started")
        logger.info(f"  - Cleanup time: {self.cleanup_time} daily")
        logger.info(f"  - Cleanup after: {self.cleanup_days} days")

        # Run an initial cleanup if there are old images
        logger.info("Running initial cleanup check...")
        self.run_cleanup()

    def stop_scheduler(self):
        """Stop the background scheduler"""
        if not self.running:
            return

        self.running = False
        schedule.clear()

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=1.0)

        logger.info("Image cleanup scheduler stopped")

    def _run_scheduler(self):
        """Internal method to run the scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)

    def get_next_cleanup_time(self) -> Optional[str]:
        """Get the next scheduled cleanup time"""
        jobs = schedule.get_jobs()
        if jobs:
            next_run = jobs[0].next_run
            if next_run:
                return next_run.strftime("%Y-%m-%d %H:%M:%S")
        return None

    def get_status(self) -> dict:
        """Get the current status of the scheduler"""
        return {
            "running": self.running,
            "cleanup_days": self.cleanup_days,
            "cleanup_time": self.cleanup_time,
            "next_cleanup": self.get_next_cleanup_time(),
            "images_directory": str(self.image_extractor.images_dir)
        }
