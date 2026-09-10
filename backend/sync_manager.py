import logging
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import requests

from backend.db import init_db, get_db, upsert_show, get_show, get_all_shows, get_setting
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

    def sync_show_generator(self, rating_key: str, force_all: bool = True, force_live: bool = False):
        """Generator that yields progress events while updating cards and posters for a show."""
        show = get_show(rating_key)
        if not show:
            yield {"type": "error", "message": f"Show with rating_key {rating_key} not found"}
            return

        mode = show.get("mode", "auto")
        if mode == "ignored":
            yield {"type": "done", "result": {"status": "skipped", "message": "Show is set to ignored"}}
            return

        episodes = self.plex.get_show_episodes(rating_key)
        tmdb_id = show.get("tmdb_id")
        is_test = TEST_MODE and not force_live

        # Fetch existing card statuses from DB for 'missing only' filtering
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT rating_key, card_source FROM episodes WHERE show_rating_key = ?", (rating_key,))
        existing_cards = {r["rating_key"]: r["card_source"] for r in cursor.fetchall()}
        conn.close()

        # Calculate episodes to process
        target_episodes = [
            ep for ep in episodes
            if force_all or existing_cards.get(ep["rating_key"]) in (None, 'none', '')
        ]

        # ----------------------------------------------------
        # MODE 1: GENERATOR ONLY (Never check MediUX)
        # ----------------------------------------------------
        if mode == "generator_only":
            logger.info(f"Running Generator-Only mode for '{show['title']}' (force_all={force_all}, live={not is_test})...")
            total_items = len(target_episodes)
            updated_count = 0
            current_item = 0

            if total_items == 0:
                yield {"type": "progress", "current": 0, "total": 0, "label": "", "message": "All cards are already up to date."}
                yield {
                    "type": "done",
                    "result": {
                        "status": "success",
                        "test_mode": is_test,
                        "force_live": force_live,
                        "force_all": force_all,
                        "mode": mode,
                        "updated_cards": 0,
                        "updated_season_posters": 0,
                        "message": "All cards are already up to date."
                    }
                }
                return

            for ep in target_episodes:
                current_item += 1
                s_num = ep["season_number"]
                e_num = ep["episode_number"]
                ep_label = f"S{s_num:02d}E{e_num:02d}"

                yield {
                    "type": "progress",
                    "current": current_item,
                    "total": total_items,
                    "label": ep_label,
                    "message": f"Updating {current_item} of {total_items} ({ep_label})"
                }

                ep_key = ep["rating_key"]
                still_file = self.tmdb.get_episode_still(tmdb_id, s_num, e_num)
                if not still_file:
                    continue

                card_img = self.renderer.render(
                    base_image_path=still_file,
                    episode_title=ep["title"],
                    season_num=s_num,
                    episode_num=e_num,
                    style_config=show
                )

                clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()
                if is_test:
                    show_test_dir = TEST_OUTPUT_DIR / clean_title
                    show_test_dir.mkdir(parents=True, exist_ok=True)
                    out_path = show_test_dir / f"S{s_num:02d}E{e_num:02d}_{ep['title'][:30]}.jpg"
                    card_img.save(out_path, quality=95)
                    logger.info(f"🧪 [TEST MODE] Saved generated card to {out_path}")

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    card_img.save(tmp.name, quality=95)
                    self.plex.upload_episode_card(ep_key, tmp.name, force_live=force_live)
                    Path(tmp.name).unlink(missing_ok=True)

                self._update_episode_card_status(ep_key, "generator_preset")
                updated_count += 1

            yield {
                "type": "done",
                "result": {
                    "status": "success",
                    "test_mode": is_test,
                    "force_live": force_live,
                    "force_all": force_all,
                    "mode": mode,
                    "updated_cards": updated_count,
                    "updated_season_posters": 0,
                    "message": f"🧪 Test Mode: Rendered {updated_count} cards locally without uploading to Plex." if is_test else f"Successfully uploaded {updated_count} cards to Plex!"
                }
            }
            return

        # ----------------------------------------------------
        # MODE 2: AUTO (Check MediUX for full season sets, fallback to generator)
        # ----------------------------------------------------
        logger.info(f"Running Auto mode for '{show['title']}' (force_all={force_all}, live={not is_test})...")
        required_seasons = list(set(ep["season_number"] for ep in episodes))
        
        # Check MediUX for matching sets
        matched_set = None
        if tmdb_id:
            all_sets = self.mediux.get_show_sets(tmdb_id)
            if show.get("mediux_set_url"):
                target = str(show["mediux_set_url"]).strip()
                for s in all_sets:
                    if s.get("set_url") == target or s.get("id") == target or f"/sets/{s.get('id')}" in target:
                        matched_set = s
                        logger.info(f"🎯 Using user-selected MediUX set {s['id']} by {s['creator']} for '{show['title']}'")
                        break
            if not matched_set:
                pref_str = get_setting("preferred_mediux_creators", "")
                pref_creators = [p.strip() for p in pref_str.split(",") if p.strip()]
                matched_set = self.mediux.find_best_matching_set(tmdb_id, required_seasons, preferred_creators=pref_creators)

        # Pre-check target season posters
        target_seasons = []
        if matched_set and matched_set.get("season_posters"):
            try:
                plex_seasons = self.plex.get_show_seasons(rating_key)
                for season in plex_seasons:
                    s_num = season["season_number"]
                    if matched_set["season_posters"].get(str(s_num)) or matched_set["season_posters"].get(s_num):
                        target_seasons.append(season)
            except Exception as e:
                logger.warning(f"Could not check seasons for '{show['title']}': {e}")

        total_items = len(target_episodes) + len(target_seasons)
        current_item = 0
        updated_count = 0
        updated_season_posters = 0

        if total_items == 0:
            yield {"type": "progress", "current": 0, "total": 0, "label": "", "message": "All cards are already up to date."}
            yield {
                "type": "done",
                "result": {
                    "status": "success",
                    "test_mode": is_test,
                    "force_live": force_live,
                    "force_all": force_all,
                    "mode": mode,
                    "mediux_set_used": matched_set["id"] if matched_set else None,
                    "updated_cards": 0,
                    "updated_season_posters": 0,
                    "message": "All cards are already up to date."
                }
            }
            return

        for ep in target_episodes:
            current_item += 1
            ep_key = ep["rating_key"]
            s_num = ep["season_number"]
            e_num = ep["episode_number"]
            ep_label = f"S{s_num:02d}E{e_num:02d}"

            yield {
                "type": "progress",
                "current": current_item,
                "total": total_items,
                "label": ep_label,
                "message": f"Updating {current_item} of {total_items} ({ep_label})"
            }
            
            mediux_card_url = None
            if matched_set:
                cards = matched_set.get("title_cards", {})
                mediux_card_url = cards.get(f"{s_num}_{e_num}") or cards.get((s_num, e_num))

            clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()

            if mediux_card_url:
                # Apply official MediUX card
                if is_test:
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

                self.plex.upload_episode_card(ep_key, mediux_card_url, force_live=force_live)
                self._update_episode_card_status(ep_key, "mediux", mediux_card_url)
                updated_count += 1
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
                    if is_test:
                        show_test_dir = TEST_OUTPUT_DIR / clean_title
                        show_test_dir.mkdir(parents=True, exist_ok=True)
                        out_path = show_test_dir / f"S{s_num:02d}E{e_num:02d}_interim.jpg"
                        card_img.save(out_path, quality=95)
                        logger.info(f"🧪 [TEST MODE] Saved interim card to {out_path}")

                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        card_img.save(tmp.name, quality=95)
                        self.plex.upload_episode_card(ep_key, tmp.name, force_live=force_live)
                        Path(tmp.name).unlink(missing_ok=True)

                    self._update_episode_card_status(ep_key, "generator_interim")
                    updated_count += 1

        # Pull Season Posters if present in MediUX set
        if target_seasons:
            clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()
            for season in target_seasons:
                current_item += 1
                s_num = season["season_number"]
                season_label = f"Season {s_num} Poster"

                yield {
                    "type": "progress",
                    "current": current_item,
                    "total": total_items,
                    "label": season_label,
                    "message": f"Updating {current_item} of {total_items} ({season_label})"
                }

                poster_url = matched_set["season_posters"].get(str(s_num)) or matched_set["season_posters"].get(s_num)
                if poster_url:
                    if is_test:
                        show_test_dir = TEST_OUTPUT_DIR / clean_title
                        show_test_dir.mkdir(parents=True, exist_ok=True)
                        out_path = show_test_dir / f"Season_{s_num:02d}_poster.jpg"
                        if not out_path.exists():
                            try:
                                r = requests.get(poster_url, timeout=10)
                                if r.status_code == 200:
                                    with open(out_path, "wb") as f:
                                        f.write(r.content)
                                    logger.info(f"🧪 [TEST MODE] Saved season {s_num} poster to {out_path}")
                            except Exception as e:
                                logger.warning(f"Could not save test season poster: {e}")

                    self.plex.upload_season_poster(season["rating_key"], poster_url, force_live=force_live)
                    updated_season_posters += 1

        poster_msg = f" and {updated_season_posters} season posters" if updated_season_posters > 0 else ""
        yield {
            "type": "done",
            "result": {
                "status": "success",
                "test_mode": is_test,
                "force_live": force_live,
                "force_all": force_all,
                "mode": mode,
                "mediux_set_used": matched_set["id"] if matched_set else None,
                "updated_cards": updated_count,
                "updated_season_posters": updated_season_posters,
                "message": f"🧪 Test Mode: Rendered {updated_count} cards{poster_msg} locally without uploading to Plex." if is_test else f"Successfully uploaded {updated_count} cards{poster_msg} to Plex!"
            }
        }

    def sync_show(self, rating_key: str, force_all: bool = True, force_live: bool = False) -> Dict[str, Any]:
        """Apply cards for a show according to its mode and style (synchronous wrapper)."""
        final_result = None
        for event in self.sync_show_generator(rating_key, force_all=force_all, force_live=force_live):
            if event.get("type") == "done":
                final_result = event.get("result")
        return final_result or {"status": "error", "message": "No result returned from sync generator"}

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
