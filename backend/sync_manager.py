import logging
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import requests

from backend.db import init_db, get_db, upsert_show, get_show, get_all_shows
from backend.plex_client import PlexClient
from backend.tmdb_client import TMDbClient
from backend.mediux_client import MediuxClient
from backend.generator.renderer import TitleCardRenderer
from backend.config import CACHE_DIR, TEST_MODE, TEST_OUTPUT_DIR

logger = logging.getLogger(__name__)

class SyncManager:
    def __init__(self):
        init_db()
        self.plex = PlexClient()
        self.tmdb = TMDbClient()
        self.mediux = MediuxClient()
        self.renderer = TitleCardRenderer()

    def scan_and_index_library(self):
        """Scan all TV shows from Plex and store in database."""
        shows = self.plex.get_all_shows()
        logger.info(f"Indexing {len(shows)} shows from Plex...")
        
        for s in shows:
            upsert_show(s)
            
            # Record episodes in database
            episodes = self.plex.get_show_episodes(s["rating_key"])
            conn = get_db()
            cursor = conn.cursor()
            for ep in episodes:
                cursor.execute("""
                INSERT INTO episodes (rating_key, show_rating_key, season_number, episode_number, title)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(rating_key) DO UPDATE SET
                    title = excluded.title,
                    updated_at = CURRENT_TIMESTAMP
                """, (ep["rating_key"], s["rating_key"], ep["season_number"], ep["episode_number"], ep["title"]))
            conn.commit()
            conn.close()

        logger.info("Library index complete.")
        return len(shows)

    def sync_show(self, rating_key: str, force: bool = False) -> Dict[str, Any]:
        """Apply cards for a show according to its mode and style."""
        show = get_show(rating_key)
        if not show:
            raise ValueError(f"Show with rating_key {rating_key} not found")

        mode = show.get("mode", "auto")
        if mode == "ignored":
            return {"status": "skipped", "message": "Show is set to ignored"}

        episodes = self.plex.get_show_episodes(rating_key)
        tmdb_id = show.get("tmdb_id")
        
        updated_count = 0
        card_sources = {}

        # ----------------------------------------------------
        # MODE 1: GENERATOR ONLY (Never check MediUX)
        # ----------------------------------------------------
        if mode == "generator_only":
            logger.info(f"Running Generator-Only mode for '{show['title']}'...")
            for ep in episodes:
                ep_key = ep["rating_key"]
                still_file = self.tmdb.get_episode_still(tmdb_id, ep["season_number"], ep["episode_number"])
                if not still_file:
                    continue

                # Render card
                card_img = self.renderer.render(
                    base_image_path=still_file,
                    episode_title=ep["title"],
                    season_num=ep["season_number"],
                    episode_num=ep["episode_number"],
                    style_config=show
                )

                # Save temporary file and upload
                clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()
                if TEST_MODE:
                    show_test_dir = TEST_OUTPUT_DIR / clean_title
                    show_test_dir.mkdir(parents=True, exist_ok=True)
                    out_path = show_test_dir / f"S{ep['season_number']:02d}E{ep['episode_number']:02d}_{ep['title'][:30]}.jpg"
                    card_img.save(out_path, quality=95)
                    logger.info(f"🧪 [TEST MODE] Saved generated card to {out_path}")

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    card_img.save(tmp.name, quality=95)
                    self.plex.upload_episode_card(ep_key, tmp.name)
                    Path(tmp.name).unlink(missing_ok=True)

                self._update_episode_card_status(ep_key, "generator_preset")
                updated_count += 1
                card_sources[ep_key] = "generator_preset"

            return {
                "status": "success",
                "test_mode": TEST_MODE,
                "mode": mode,
                "updated_cards": updated_count,
                "message": "🧪 Test Mode: Rendered cards locally without uploading to Plex." if TEST_MODE else "Applied cards to Plex."
            }

        # ----------------------------------------------------
        # MODE 2: AUTO (Check MediUX for full season sets, fallback to generator)
        # ----------------------------------------------------
        logger.info(f"Running Auto mode for '{show['title']}'...")
        required_seasons = list(set(ep["season_number"] for ep in episodes))
        
        # Check MediUX for matching sets
        matched_set = None
        if tmdb_id:
            matched_set = self.mediux.find_best_matching_set(tmdb_id, required_seasons)

        for ep in episodes:
            ep_key = ep["rating_key"]
            s_num = ep["season_number"]
            e_num = ep["episode_number"]
            
            mediux_card_url = None
            if matched_set and (s_num, e_num) in matched_set.get("title_cards", {}):
                mediux_card_url = matched_set["title_cards"][(s_num, e_num)]

            if mediux_card_url:
                # Apply official MediUX card
                clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()
                if TEST_MODE:
                    show_test_dir = TEST_OUTPUT_DIR / clean_title
                    show_test_dir.mkdir(parents=True, exist_ok=True)
                    out_path = show_test_dir / f"S{s_num:02d}E{e_num:02d}_mediux.jpg"
                    if not out_path.exists():
                        try:
                            r = requests.get(mediux_card_url, timeout=10)
                            if r.status_code == 200:
                                with open(out_path, "wb") as f:
                                    f.write(r.content)
                                logger.info(f"🧪 [TEST MODE] Saved MediUX card to {out_path}")
                        except Exception as e:
                            logger.warning(f"Could not save test MediUX card: {e}")

                self.plex.upload_episode_card(ep_key, mediux_card_url)
                self._update_episode_card_status(ep_key, "mediux", mediux_card_url)
                updated_count += 1
                card_sources[ep_key] = "mediux"
            else:
                # Fallback: Render clean interim card using preset
                still_file = self.tmdb.get_episode_still(tmdb_id, s_num, e_num)
                if still_file:
                    card_img = self.renderer.render(
                        base_image_path=still_file,
                        episode_title=ep["title"],
                        season_num=s_num,
                        episode_num=e_num,
                        style_config=show
                    )
                    clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()
                    if TEST_MODE:
                        show_test_dir = TEST_OUTPUT_DIR / clean_title
                        show_test_dir.mkdir(parents=True, exist_ok=True)
                        out_path = show_test_dir / f"S{s_num:02d}E{e_num:02d}_interim.jpg"
                        card_img.save(out_path, quality=95)
                        logger.info(f"🧪 [TEST MODE] Saved interim card to {out_path}")

                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        card_img.save(tmp.name, quality=95)
                        self.plex.upload_episode_card(ep_key, tmp.name)
                        Path(tmp.name).unlink(missing_ok=True)

                    self._update_episode_card_status(ep_key, "generator_interim")
                    updated_count += 1
                    card_sources[ep_key] = "generator_interim"

        return {
            "status": "success",
            "test_mode": TEST_MODE,
            "mode": mode,
            "mediux_set_used": matched_set["id"] if matched_set else None,
            "updated_cards": updated_count,
            "message": "🧪 Test Mode: Rendered and verified cards locally without uploading to Plex." if TEST_MODE else "Applied cards to Plex."
        }

    def _update_episode_card_status(self, episode_rating_key: str, source: str, card_url: Optional[str] = None):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE episodes
        SET card_source = ?, card_url = ?, updated_at = CURRENT_TIMESTAMP
        WHERE rating_key = ?
        """, (source, card_url, episode_rating_key))
        conn.commit()
        conn.close()
