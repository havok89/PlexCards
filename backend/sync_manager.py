import logging
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import requests

from backend.db import init_db, get_db, upsert_show, get_show, get_all_shows, get_setting, get_show_season_posters, record_season_poster
from backend.plex_client import PlexClient
from backend.tmdb_client import TMDbClient
from backend.mediux_client import MediuxClient
from backend.generator.renderer import TitleCardRenderer
from backend.config import CACHE_DIR, STILLS_DIR, TEST_MODE, TEST_OUTPUT_DIR

logger = logging.getLogger(__name__)

class SyncManager:
    def __init__(self):
        init_db()
        self.plex = PlexClient()
        self.tmdb = TMDbClient()
        self.mediux = MediuxClient()
        self.renderer = TitleCardRenderer()

    def get_episode_backdrop_still(self, show: Dict[str, Any], ep: Dict[str, Any]) -> Optional[Path]:
        """
        Cascade to find or generate the best available still image for an episode card:
        1. TMDb official episode promotional still
        2. Clean show backdrop art (from TMDb or Plex show art)
        3. Plex episode video thumbnail (last-resort fallback if no clean show art exists)
        4. Clean cinematic dark canvas
        """
        tmdb_id = show.get("tmdb_id")
        s_num = ep.get("season_number")
        e_num = ep.get("episode_number")

        # 1. Official TMDb episode still
        if tmdb_id and s_num is not None and e_num is not None:
            try:
                still_file = self.tmdb.get_episode_still(tmdb_id, s_num, e_num)
                if still_file and still_file.exists():
                    return still_file
            except Exception as e:
                logger.warning(f"Failed to fetch TMDb still for {show.get('title')} S{s_num:02d}E{e_num:02d}: {e}")

        # 2. Clean Show backdrop art (from TMDb or Plex show art)
        # We prioritize high-resolution, textless show backdrop art over Plex thumbnails,
        # because Plex thumbnails frequently contain old title cards from other programs or low-res captures.
        show_key = show.get("rating_key", "default")
        backdrop_url = show.get("backdrop_url")
        if not backdrop_url and tmdb_id:
            try:
                details = self.tmdb.get_show_details(tmdb_id)
                if details:
                    backdrop_url = details.get("backdrop_url")
            except Exception:
                pass

        if not backdrop_url and show_key != "default":
            try:
                plex_item = self.plex.server.fetchItem(int(show_key))
                if getattr(plex_item, "artUrl", None):
                    backdrop_url = plex_item.artUrl
            except Exception:
                pass

        if backdrop_url:
            backdrop_path = STILLS_DIR / f"backdrop_{show_key}.jpg"
            if backdrop_path.exists():
                return backdrop_path
            try:
                r = requests.get(backdrop_url, timeout=15)
                if r.status_code == 200:
                    with open(backdrop_path, "wb") as f:
                        f.write(r.content)
                    logger.info(f"🎨 Used clean show backdrop fallback for {show.get('title')} S{s_num:02d}E{e_num:02d}")
                    return backdrop_path
            except Exception as e:
                logger.warning(f"Could not download show backdrop for show {show_key}: {e}")

        # 3. Plex episode thumbnail (fallback only if no TMDb episode still or show backdrop exists)
        ep_key = ep.get("rating_key")
        thumb_url = ep.get("thumb_url")
        if thumb_url and ep_key:
            plex_still_path = STILLS_DIR / f"plex_{ep_key}.jpg"
            if plex_still_path.exists():
                return plex_still_path
            try:
                r = requests.get(thumb_url, timeout=15)
                if r.status_code == 200:
                    with open(plex_still_path, "wb") as f:
                        f.write(r.content)
                    logger.info(f"📸 Used Plex thumbnail fallback for {show.get('title')} S{s_num:02d}E{e_num:02d}")
                    return plex_still_path
            except Exception as e:
                logger.warning(f"Could not download Plex thumbnail for episode {ep_key}: {e}")

        # 4. Cinematic dark canvas fallback
        canvas_path = STILLS_DIR / "generic_canvas.jpg"
        if not canvas_path.exists():
            try:
                from PIL import Image
                img = Image.new("RGB", (1920, 1080), (18, 20, 26))
                img.save(canvas_path, quality=95)
            except Exception as e:
                logger.warning(f"Could not create generic canvas fallback: {e}")
                return None
        return canvas_path

    def get_show_logo_path(self, show: Dict[str, Any]) -> Optional[Path]:
        """Fetch or return cached transparent PNG logo for a show."""
        tmdb_id = show.get("tmdb_id")
        if tmdb_id:
            try:
                return self.tmdb.get_show_logo(int(tmdb_id))
            except Exception as e:
                logger.warning(f"Could not load logo for show {show.get('title')}: {e}")
        return None

    def scan_and_index_library(self):
        """Scan all TV shows from Plex and store in database. Auto-matches shows with TMDb if Plex has no TMDb ID."""
        shows = self.plex.get_all_shows()
        logger.info(f"Indexing {len(shows)} shows from Plex...")
        
        for s in shows:
            # If Plex did not provide a TMDb ID (e.g. local:// guid), attempt automatic TMDb search match
            if not s.get("tmdb_id") and s.get("title"):
                try:
                    search_results = self.tmdb.search_shows(s["title"], year=s.get("year"))
                    if not search_results and s.get("year"):
                        # Fallback without year constraint
                        search_results = self.tmdb.search_shows(s["title"])
                    if search_results:
                        top = search_results[0]
                        s["tmdb_id"] = top["tmdb_id"]
                        if not s.get("poster_url") and top.get("poster_url"):
                            s["poster_url"] = top["poster_url"]
                        if not s.get("backdrop_url") and top.get("backdrop_url"):
                            s["backdrop_url"] = top["backdrop_url"]
                        logger.info(f"🎯 Auto-matched '{s['title']}' to TMDb ID {s['tmdb_id']} ('{top.get('name')}', {top.get('year')})")
                except Exception as e:
                    logger.warning(f"Could not auto-match TMDb ID for '{s['title']}': {e}")

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
        try:
            self.sync_show_statuses()
        except Exception as e:
            logger.warning(f"Could not complete TMDb status sync: {e}")
        return len(shows)

    def sync_show_statuses(self):
        """Fetch and update TV show broadcast status (Returning Series, Ended, Canceled) from TMDb."""
        from concurrent.futures import ThreadPoolExecutor
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT rating_key, tmdb_id FROM shows WHERE tmdb_id IS NOT NULL")
        shows_to_check = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not shows_to_check or not self.tmdb.api_key:
            return

        def _fetch_status(item):
            rk, tid = item["rating_key"], item["tmdb_id"]
            try:
                url = f"{self.tmdb.BASE_URL}/tv/{tid}?api_key={self.tmdb.api_key}"
                r = requests.get(url, timeout=6)
                if r.status_code == 200:
                    d = r.json()
                    st = d.get("status")
                    if st:
                        return rk, st
            except Exception:
                pass
            return rk, None

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(_fetch_status, shows_to_check))

        conn = get_db()
        cursor = conn.cursor()
        updated_count = 0
        for rk, st in results:
            if st:
                cursor.execute("UPDATE shows SET status = ? WHERE rating_key = ?", (st, str(rk)))
                updated_count += 1
        conn.commit()
        conn.close()
        logger.info(f"Updated status for {updated_count} shows from TMDb.")

    def sync_show_generator(self, rating_key: str, force_all: bool = True, force_live: bool = False):
        """Generator that yields progress events while updating cards and posters for a show."""
        show = get_show(rating_key)
        if not show:
            yield {"type": "error", "message": f"Show with rating_key {rating_key} not found"}
            return

        # Tell real-time listener to ignore feedback events for this show while we upload
        try:
            from backend.plex_listener import plex_listener
            plex_listener.ignore_show(rating_key, duration=60.0)
        except Exception:
            pass

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
                still_file = self.get_episode_backdrop_still(show, ep)
                if not still_file:
                    continue

                card_img = self.renderer.render(
                    base_image_path=still_file,
                    episode_title=ep["title"],
                    season_num=s_num,
                    episode_num=e_num,
                    style_config=show,
                    logo_image_path=self.get_show_logo_path(show)
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

        # In Auto mode, when syncing missing only (force_all=False), also upgrade any episode
        # that currently has a temporary generator_interim card if the matched MediUX set now has an official card
        if mode == "auto" and not force_all and matched_set:
            cards = matched_set.get("title_cards", {})
            existing_ep_keys = {ep["rating_key"] for ep in target_episodes}
            for ep in episodes:
                ep_key = ep["rating_key"]
                if ep_key in existing_ep_keys:
                    continue
                s_num = ep["season_number"]
                e_num = ep["episode_number"]
                has_mediux = bool(cards.get(f"{s_num}_{e_num}") or cards.get((s_num, e_num)))
                if has_mediux and existing_cards.get(ep_key) == "generator_interim":
                    target_episodes.append(ep)
                    existing_ep_keys.add(ep_key)

        # Pre-check target season posters
        target_seasons = []
        existing_season_posters = get_show_season_posters(rating_key)
        if matched_set and matched_set.get("season_posters"):
            try:
                plex_seasons = self.plex.get_show_seasons(rating_key)
                for season in plex_seasons:
                    s_num = season["season_number"]
                    poster_url = matched_set["season_posters"].get(str(s_num)) or matched_set["season_posters"].get(s_num)
                    if not poster_url:
                        continue

                    already_recorded = existing_season_posters.get(s_num) == poster_url
                    already_has_plex_art = season.get("has_poster", False)

                    if not force_all and (already_recorded or already_has_plex_art):
                        if not already_recorded:
                            record_season_poster(season["rating_key"], rating_key, s_num, poster_url)
                        continue

                    target_seasons.append((season, poster_url))
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
                still_file = self.get_episode_backdrop_still(show, ep)
                if still_file:
                    card_img = self.renderer.render(
                        base_image_path=still_file,
                        episode_title=ep["title"],
                        season_num=s_num,
                        episode_num=e_num,
                        style_config=show,
                        logo_image_path=self.get_show_logo_path(show)
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
            for season, poster_url in target_seasons:
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

                try:
                    from backend.plex_listener import plex_listener
                    plex_listener.ignore_show(rating_key, duration=30.0)
                except Exception:
                    pass
                self.plex.upload_season_poster(season["rating_key"], poster_url, force_live=force_live)
                record_season_poster(season["rating_key"], rating_key, s_num, poster_url)
                updated_season_posters += 1

        poster_msg = f" and {updated_season_posters} season posters" if updated_season_posters > 0 else ""
        try:
            from backend.plex_listener import plex_listener
            plex_listener.ignore_show(rating_key, duration=30.0)
        except Exception:
            pass
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
