import logging
from apscheduler.schedulers.background import BackgroundScheduler
from backend.config import POLL_INTERVAL_HOURS
from backend.sync_manager import SyncManager
from backend.db import get_all_shows

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
sync_manager = SyncManager()

def periodic_library_job():
    logger.info("Starting scheduled background sync job...")
    try:
        sync_manager.scan_and_index_library()
        shows = get_all_shows()
        for s in shows:
            mode = s.get("mode", "auto")
            if mode != "ignored":
                # Process missing cards and auto-upgrade interim cards without re-processing already complete ones
                sync_manager.sync_show(s["rating_key"], force_all=False)
        logger.info("Scheduled sync job finished successfully.")
    except Exception as e:
        logger.error(f"Error in background sync job: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            periodic_library_job,
            "interval",
            hours=POLL_INTERVAL_HOURS,
            id="library_sync_job",
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Background scheduler started with {POLL_INTERVAL_HOURS}h interval.")
