import logging
import threading
import time
from typing import Dict, Optional, Any

from backend.config import PLEX_TV_LIBRARY, TEST_MODE
from backend.plex_client import PlexClient
from backend.sync_manager import SyncManager
from backend.db import get_db, get_show, upsert_show, get_setting

logger = logging.getLogger(__name__)

class PlexAlertListenerDaemon:
    """Background daemon that connects to Plex's notification WebSocket
    and triggers immediate title card generation when new episodes arrive.
    """

    def __init__(self):
        self.plex = PlexClient()
        self.sync_manager = SyncManager()
        self._listener = None
        self._thread = None
        self._stop_event = threading.Event()
        self._connected = False
        self._tv_section_id: Optional[str] = None
        self._debounce_timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._listener is not None and self._listener.is_alive()

    def start(self):
        """Start the background daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.info("Plex AlertListener daemon is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="PlexAlertListenerDaemon", daemon=True)
        self._thread.start()
        logger.info("Started Plex AlertListener background daemon.")

    def stop(self):
        """Stop the background daemon and disconnect the listener."""
        self._stop_event.set()
        with self._lock:
            for timer in self._debounce_timers.values():
                timer.cancel()
            self._debounce_timers.clear()

        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                logger.debug(f"Error stopping AlertListener: {e}")
            self._listener = None

        self._connected = False
        logger.info("Stopped Plex AlertListener background daemon.")

    def _resolve_tv_section_id(self):
        """Find the numeric ID of the configured TV library section."""
        try:
            sec = self.plex.get_tv_section()
            self._tv_section_id = str(sec.key)
            logger.info(f"Target Plex TV Library: '{sec.title}' (Section ID: {self._tv_section_id})")
        except Exception as e:
            logger.warning(f"Could not resolve Plex TV section ID: {e}")
            self._tv_section_id = None

    def _run_loop(self):
        """Resilient connection loop that reconnects on disconnect or error."""
        while not self._stop_event.is_set():
            try:
                if not self._tv_section_id:
                    self._resolve_tv_section_id()

                logger.info("Connecting to Plex notification WebSocket at %s...", self.plex.base_url)
                self._listener = self.plex.server.startAlertListener(
                    callback=self._on_message,
                    callbackError=self._on_error
                )
                self._connected = True
                logger.info("🟢 Plex AlertListener connected! Listening for new episodes in real time.")

                # Keep monitor thread alive while listener is running
                while not self._stop_event.is_set() and self._listener.is_alive():
                    self._stop_event.wait(timeout=2.0)

            except Exception as e:
                logger.warning(f"Plex AlertListener connection failed: {e}")
            finally:
                self._connected = False
                if self._listener:
                    try:
                        self._listener.stop()
                    except Exception:
                        pass
                    self._listener = None

            if not self._stop_event.is_set():
                logger.info("Plex AlertListener disconnected. Reconnecting in 10 seconds...")
                self._stop_event.wait(timeout=10.0)

    def _on_error(self, error):
        logger.warning(f"Plex AlertListener error: {error}")

    def _on_message(self, data: Dict[str, Any]):
        """Parse incoming Plex alert notifications."""
        msg_type = data.get("type")
        if not msg_type:
            return

        # Timeline notifications report items created, updated, matched, or processed
        if msg_type == "timeline":
            entries = data.get("TimelineEntry", [])
            for entry in entries:
                self._handle_timeline_entry(entry)

    def _handle_timeline_entry(self, entry: Dict[str, Any]):
        identifier = entry.get("identifier")
        if identifier != "com.plexapp.plugins.library":
            return

        sec_id = entry.get("sectionID")
        # If sectionID is present and doesn't match our TV library, ignore
        if sec_id and self._tv_section_id and str(sec_id) != str(self._tv_section_id):
            return

        state = entry.get("state")
        # state 0: created, 5: processed, 2: matched, 4: metadata processed
        if state not in (0, 4, 5):
            return

        item_id = entry.get("itemID")
        if not item_id:
            return

        # Spawn a thread to inspect item and schedule sync without blocking websocket
        threading.Thread(
            target=self._process_media_item,
            args=(str(item_id),),
            daemon=True
        ).start()

    def _process_media_item(self, item_id: str):
        try:
            item = self.plex.server.fetchItem(int(item_id))
            if not item:
                return

            # Verify library section
            if self._tv_section_id and str(item.librarySectionID) != str(self._tv_section_id):
                return

            item_type = getattr(item, 'type', None)

            if item_type == 'episode':
                show = item.show()
                show_key = str(show.ratingKey)
                s_num = item.seasonNumber
                e_num = item.index
                ep_title = item.title or f"Episode {e_num}"
                ep_key = str(item.ratingKey)

                # Record newly found episode in SQLite database
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO episodes (rating_key, show_rating_key, season_number, episode_number, title)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(rating_key) DO UPDATE SET
                    title = excluded.title,
                    updated_at = CURRENT_TIMESTAMP
                """, (ep_key, show_key, s_num, e_num, ep_title))
                conn.commit()
                conn.close()

                logger.info(f"✨ Real-time alert: Detected S{s_num:02d}E{e_num:02d} '{ep_title}' for '{show.title}'")
                self._schedule_show_sync(show_key, show.title)

            elif item_type == 'show':
                show_key = str(item.ratingKey)
                logger.info(f"✨ Real-time alert: Detected update for show '{item.title}'")
                self._schedule_show_sync(show_key, item.title)

            elif item_type == 'season':
                show = item.show()
                show_key = str(show.ratingKey)
                logger.info(f"✨ Real-time alert: Detected season update for '{show.title}'")
                self._schedule_show_sync(show_key, show.title)

        except Exception as e:
            logger.debug(f"Could not inspect timeline item {item_id}: {e}")

    def _schedule_show_sync(self, show_key: str, show_title: str):
        """Debounce sync triggers per show by 5 seconds so batch episodes sync cleanly together."""
        with self._lock:
            if show_key in self._debounce_timers:
                self._debounce_timers[show_key].cancel()

            timer = threading.Timer(5.0, self._execute_show_sync, args=(show_key, show_title))
            self._debounce_timers[show_key] = timer
            timer.daemon = True
            timer.start()
            logger.info(f"⏳ Buffering sync for '{show_title}' (5s debounce window)...")

    def _execute_show_sync(self, show_key: str, show_title: str):
        with self._lock:
            self._debounce_timers.pop(show_key, None)

        try:
            logger.info(f"⚡ Live Trigger: Processing cards for '{show_title}' ({show_key})...")
            show = get_show(show_key)

            # If show is brand new and not yet in database, index it first
            if not show:
                logger.info(f"New show '{show_title}' not found in database. Running library index...")
                self.sync_manager.scan_and_index_library()
                show = get_show(show_key)
                if not show:
                    logger.warning(f"Could not locate show '{show_title}' after index.")
                    return

            mode = show.get("mode", "auto")
            if mode == "ignored":
                logger.info(f"Show '{show_title}' is set to 'ignored'. Skipping title card generation.")
                return

            # Sync ONLY missing cards and posters
            is_live = not TEST_MODE
            result = self.sync_manager.sync_show(show_key, force_all=False, force_live=is_live)
            logger.info(f"🎉 Live sync finished for '{show_title}': {result.get('message')}")

        except Exception as e:
            logger.error(f"Error executing live sync for '{show_title}': {e}")


# Singleton instance
plex_listener = PlexAlertListenerDaemon()
