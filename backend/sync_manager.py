import logging
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import requests

from backend.db import (
    init_db, get_db, upsert_show, get_show, get_all_shows, get_setting,
    get_show_season_posters, record_season_poster, update_show_mode,
    get_effective_style
)
from backend.plex_client import PlexClient
from backend.tmdb_client import TMDbClient
from backend.tvdb_client import TVDbClient
from backend.mediux_client import MediuxClient
from backend.generator.renderer import TitleCardRenderer
from backend.config import CACHE_DIR, STILLS_DIR, TEST_MODE, TEST_OUTPUT_DIR

logger = logging.getLogger(__name__)

class SyncManager:
    def __init__(self):
        init_db()
        self.plex = PlexClient()
        self.tmdb = TMDbClient()
        self.tvdb = TVDbClient()
        self.mediux = MediuxClient()
        self.renderer = TitleCardRenderer()

    def get_episode_backdrop_still(self, show: Dict[str, Any], ep: Dict[str, Any]) -> Optional[Path]:
        """
        Cascade to find or generate the best available still image for an episode card:
        Prioritizes TVDB or TMDb based on user settings (defaulting to tvdb).
        1. Primary provider episode still (or user custom selected candidate still)
        2. Secondary provider episode still
        3. Clean show backdrop art (from TVDB / TMDb or Plex show art)
        4. Plex episode video thumbnail (last-resort fallback)
        5. Clean cinematic dark canvas
        """
        tvdb_id = show.get("tvdb_id")
        tmdb_id = show.get("tmdb_id")
        s_num = ep.get("season_number")
        e_num = ep.get("episode_number")
        rk = str(show.get("rating_key", ""))
        priority = get_setting("metadata_provider_priority", "tvdb").lower()

        # Check for user-selected override first
        from backend.db import get_episode_still_override, set_episode_still_override
        override_path = get_episode_still_override(rk, s_num, e_num) if (rk and s_num is not None and e_num is not None) else None

        # 0. If override is a custom uploaded still or local file
        if override_path and (override_path.startswith("custom:") or override_path.startswith("custom_")):
            clean_filename = override_path.replace("custom:", "").split("?")[0]
            custom_file = STILLS_DIR / clean_filename
            if custom_file.exists():
                return custom_file
        if override_path and Path(override_path).is_absolute() and Path(override_path).exists():
            return Path(override_path)

        # 1. If override is an explicit TVDB URL
        if override_path and (override_path.startswith("http://") or override_path.startswith("https://")) and tvdb_id:
            still_file = self.tvdb.get_episode_still(int(tvdb_id), s_num, e_num, specific_still_url=override_path)
            if still_file and still_file.exists():
                return still_file

        # 2. If override is a TMDb file path
        if override_path and not override_path.startswith("http") and not override_path.startswith("custom") and tmdb_id:
            still_file = self.tmdb.get_episode_still(int(tmdb_id), s_num, e_num, specific_still_path=override_path)
            if still_file and still_file.exists():
                return still_file

        def _fetch_tvdb_still() -> Optional[Path]:
            if tvdb_id and s_num is not None and e_num is not None and self.tvdb.is_configured:
                try:
                    target_url = override_path if (override_path and override_path.startswith("http")) else None
                    still_file = self.tvdb.get_episode_still(int(tvdb_id), s_num, e_num, specific_still_url=target_url)
                    if still_file and still_file.exists():
                        return still_file
                except Exception as e:
                    logger.warning(f"Failed to fetch TVDB still for {show.get('title')} S{s_num:02d}E{e_num:02d}: {e}")
            return None

        def _fetch_tmdb_still() -> Optional[Path]:
            if tmdb_id and s_num is not None and e_num is not None and self.tmdb.api_key:
                try:
                    target_still = override_path if (override_path and not override_path.startswith("http")) else None
                    if not target_still and rk:
                        auto_smart_pick = get_setting("auto_smart_pick_stills", "true").lower() == "true"
                        if auto_smart_pick:
                            candidate_stills = self.tmdb.get_episode_stills_list(int(tmdb_id), s_num, e_num)
                            if candidate_stills:
                                best_still = candidate_stills[0]["file_path"]
                                target_still = best_still
                                set_episode_still_override(rk, s_num, e_num, best_still)
                    still_file = self.tmdb.get_episode_still(int(tmdb_id), s_num, e_num, specific_still_path=target_still)
                    if still_file and still_file.exists():
                        return still_file
                except Exception as e:
                    logger.warning(f"Failed to fetch TMDb still for {show.get('title')} S{s_num:02d}E{e_num:02d}: {e}")
            return None

        # Execute in order of configured provider priority
        primary_fn = _fetch_tvdb_still if priority == "tvdb" else _fetch_tmdb_still
        secondary_fn = _fetch_tmdb_still if priority == "tvdb" else _fetch_tvdb_still

        still = primary_fn() or secondary_fn()
        if still and still.exists():
            return still

        # 3. Clean Show backdrop art (from TMDb or Plex show art)
        show_key = show.get("rating_key", "default")
        backdrop_url = show.get("backdrop_url")
        if not backdrop_url and tmdb_id:
            try:
                details = self.tmdb.get_show_details(int(tmdb_id))
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

        # 4. Plex episode thumbnail (fallback only if no provider episode still or show backdrop exists)
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

        # 5. Cinematic dark canvas fallback
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
        """Fetch or return cached transparent PNG logo for a show (checking TVDB & TMDb according to priority)."""
        tmdb_id = show.get("tmdb_id")
        tvdb_id = show.get("tvdb_id")
        priority = get_setting("metadata_provider_priority", "tvdb").lower()

        def _try_tmdb() -> Optional[Path]:
            if tmdb_id:
                try:
                    return self.tmdb.get_show_logo(int(tmdb_id))
                except Exception as e:
                    logger.warning(f"Could not load TMDb logo for {show.get('title')}: {e}")
            return None

        def _try_tvdb() -> Optional[Path]:
            if tvdb_id and self.tvdb.is_configured:
                try:
                    return self.tvdb.get_show_logo(int(tvdb_id))
                except Exception as e:
                    logger.warning(f"Could not load TVDB logo for {show.get('title')}: {e}")
            return None

        primary_logo = _try_tvdb if priority == "tvdb" else _try_tmdb
        secondary_logo = _try_tmdb if priority == "tvdb" else _try_tvdb

        logo = primary_logo() or secondary_logo()
        if logo and logo.exists():
            return logo
        return None

    def scan_and_index_library(self, target_library: Optional[str] = None):
        """Scan all TV shows from Plex and store in database. Cross-references TVDB and TMDb IDs automatically."""
        if target_library and str(target_library).lower() == "all":
            all_sections = self.plex.get_tv_sections()
            shows = []
            for sec in all_sections:
                try:
                    shows.extend(self.plex.get_all_shows(target_library=sec["key"]))
                except Exception as e:
                    logger.warning(f"Failed to scan section {sec.get('title')}: {e}")
        else:
            shows = self.plex.get_all_shows(target_library=target_library)

        logger.info(f"Indexing {len(shows)} shows from Plex...")
        
        for s in shows:
            # 1. If show has tvdb_id but no tmdb_id, resolve tmdb_id via TVDB remote IDs (enables MediUX!)
            if s.get("tvdb_id") and not s.get("tmdb_id") and self.tvdb.is_configured:
                try:
                    resolved_tmdb = self.tvdb.resolve_tmdb_id(int(s["tvdb_id"]))
                    if resolved_tmdb:
                        s["tmdb_id"] = resolved_tmdb
                        logger.info(f"🔗 Auto-resolved TMDb ID {resolved_tmdb} for '{s['title']}' via TVDB ID {s['tvdb_id']}")
                except Exception as e:
                    logger.warning(f"Could not resolve TMDb ID from TVDB for '{s['title']}': {e}")

            # 2. If show has tmdb_id but no tvdb_id, resolve tvdb_id via TVDB remote ID lookup
            if s.get("tmdb_id") and not s.get("tvdb_id") and self.tvdb.is_configured:
                try:
                    resolved_tvdb = self.tvdb.resolve_tvdb_id_from_remote(str(s["tmdb_id"]))
                    if resolved_tvdb:
                        s["tvdb_id"] = resolved_tvdb
                        logger.info(f"🔗 Auto-resolved TVDB ID {resolved_tvdb} for '{s['title']}' via TMDb ID {s['tmdb_id']}")
                except Exception as e:
                    logger.warning(f"Could not resolve TVDB ID from TMDb for '{s['title']}': {e}")

            # 3. If neither provided, attempt automatic search match
            if not s.get("tmdb_id") and s.get("title"):
                try:
                    search_results = self.tmdb.search_shows(s["title"], year=s.get("year"))
                    if not search_results and s.get("year"):
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
        """Fetch and update TV show broadcast status (Returning Series, Continuing, Ended, Canceled) respecting provider priority."""
        from concurrent.futures import ThreadPoolExecutor
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT rating_key, tmdb_id, tvdb_id FROM shows")
        shows_to_check = [dict(r) for r in cursor.fetchall()]
        conn.close()

        if not shows_to_check:
            return

        priority = get_setting("metadata_provider_priority", "tvdb").lower()

        def _fetch_status(item):
            rk = item["rating_key"]
            tid = item.get("tmdb_id")
            tv_id = item.get("tvdb_id")

            def _get_tvdb_status():
                if tv_id and self.tvdb.is_configured:
                    try:
                        st = self.tvdb.get_series_status(int(tv_id))
                        if st:
                            return st
                    except Exception:
                        pass
                return None

            def _get_tmdb_status():
                if tid and self.tmdb.api_key:
                    try:
                        url = f"{self.tmdb.BASE_URL}/tv/{tid}?api_key={self.tmdb.api_key}"
                        r = requests.get(url, timeout=6)
                        if r.status_code == 200:
                            return r.json().get("status")
                    except Exception:
                        pass
                return None

            primary = _get_tvdb_status if priority == "tvdb" else _get_tmdb_status
            secondary = _get_tmdb_status if priority == "tvdb" else _get_tvdb_status
            st = primary() or secondary()
            return rk, st

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
        logger.info(f"Updated status for {updated_count} shows (prioritizing {priority.upper()}).")

    def _dispatch_sync_notifications(
        self,
        show: Dict[str, Any],
        synced_episodes_log: list,
        matched_set: Optional[Dict[str, Any]] = None,
        trigger_source: str = "manual"
    ):
        """Dispatches single or consolidated batch Discord notifications for updated episode cards."""
        if not synced_episodes_log:
            return
        try:
            from backend.discord_notifier import discord_notifier
            if not discord_notifier.is_configured:
                return

            is_manual = (trigger_source == "manual")
            creator = matched_set.get("creator") if matched_set else None
            set_url = matched_set.get("set_url") if matched_set else None
            library_name = show.get("library_name")

            is_test = bool(TEST_MODE)
            if len(synced_episodes_log) == 1:
                ep_info = synced_episodes_log[0]
                discord_notifier.notify_episode_card(
                    show_title=show["title"],
                    season_number=ep_info["season_number"],
                    episode_number=ep_info["episode_number"],
                    episode_title=ep_info["title"],
                    source=ep_info["source"],
                    card_image_path_or_url=ep_info.get("card_url"),
                    card_image_bytes=ep_info.get("image_bytes"),
                    creator=creator,
                    set_url=set_url,
                    library_name=library_name,
                    is_manual=is_manual,
                    is_test=is_test
                )
            else:
                seasons = sorted(list(set(e["season_number"] for e in synced_episodes_log)))
                for s in seasons:
                    s_eps = [e for e in synced_episodes_log if e["season_number"] == s]
                    ep_nums = sorted([e["episode_number"] for e in s_eps])
                    if len(ep_nums) == 1:
                        ep_range = f"E{ep_nums[0]:02d}"
                    else:
                        ep_range = f"E{min(ep_nums):02d}–E{max(ep_nums):02d}"

                    hero_ep = s_eps[0]
                    discord_notifier.notify_batch_cards_grouped(
                        show_title=show["title"],
                        season_number=s,
                        episodes_count=len(s_eps),
                        ep_range=ep_range,
                        source=hero_ep["source"],
                        creator=creator,
                        set_url=set_url,
                        hero_image_path_or_url=hero_ep.get("card_url"),
                        hero_image_bytes=hero_ep.get("image_bytes"),
                        library_name=library_name,
                        is_manual=is_manual,
                        is_test=is_test
                    )
        except Exception as e:
            logger.warning(f"Error dispatching Discord notifications for '{show.get('title')}': {e}")

    def sync_show_generator(
        self,
        rating_key: str,
        force_all: bool = True,
        force_live: bool = False,
        source_mode: Optional[str] = None,
        trigger_source: str = "manual"
    ):
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

        mode = source_mode or show.get("mode", "auto")
        is_test = TEST_MODE and not force_live

        if mode == "ignored":
            # If the user explicitly called apply/simulate on this show, automatically activate it
            if force_all or source_mode is not None:
                has_mediux = bool(show.get("mediux_set_url")) or bool(
                    self.mediux.get_show_sets(show.get("tmdb_id")) if show.get("tmdb_id") else False
                )
                mode = "auto" if has_mediux else "generator_only"
                if force_live:
                    update_show_mode(rating_key, mode, show.get("mediux_set_url"))
                logger.info(f"Show '{show['title']}' was 'ignored' but explicit apply was triggered; running as '{mode}'.")
            else:
                yield {
                    "type": "done",
                    "result": {
                        "status": "skipped",
                        "test_mode": is_test,
                        "force_live": force_live,
                        "force_all": force_all,
                        "mode": mode,
                        "updated_cards": 0,
                        "updated_season_posters": 0,
                        "message": f"Show '{show['title']}' is set to ignored."
                    }
                }
                return

        episodes = []
        try:
            episodes = self.plex.get_show_episodes(rating_key)
        except Exception as e:
            logger.warning(f"Could not fetch episodes from Plex API for show {rating_key}: {e}. Falling back to database episodes.")
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT rating_key, season_number, episode_number, title FROM episodes WHERE show_rating_key = ? ORDER BY season_number, episode_number",
                (rating_key,)
            )
            episodes = [dict(r) for r in cursor.fetchall()]
            conn.close()

        if not episodes:
            yield {"type": "progress", "current": 0, "total": 0, "label": "", "message": "No episodes found for this show."}
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
                    "message": "No episodes found for this show."
                }
            }
            return

        tmdb_id = show.get("tmdb_id")

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
            synced_episodes_log = []

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

                season_style = get_effective_style(rating_key, s_num)
                card_img = self.renderer.render(
                    base_image_path=still_file,
                    episode_title=ep["title"],
                    season_num=s_num,
                    episode_num=e_num,
                    style_config=season_style,
                    logo_image_path=self.get_show_logo_path(show)
                )

                clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()
                if is_test:
                    show_test_dir = TEST_OUTPUT_DIR / clean_title
                    show_test_dir.mkdir(parents=True, exist_ok=True)
                    out_path = show_test_dir / f"S{s_num:02d}E{e_num:02d}_{ep['title'][:30]}.jpg"
                    card_img.save(out_path, quality=95)
                    logger.info(f"🧪 [TEST MODE] Saved generated card to {out_path}")

                card_bytes = None
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    card_img.save(tmp.name, quality=95)
                    self.plex.upload_episode_card(ep_key, tmp.name, force_live=force_live)
                    try:
                        card_bytes = Path(tmp.name).read_bytes()
                    except Exception:
                        pass
                    Path(tmp.name).unlink(missing_ok=True)

                self._update_episode_card_status(ep_key, "generator_preset")
                updated_count += 1
                synced_episodes_log.append({
                    "season_number": s_num,
                    "episode_number": e_num,
                    "title": ep["title"],
                    "source": "generator",
                    "image_bytes": card_bytes
                })

            self._dispatch_sync_notifications(show, synced_episodes_log, trigger_source=trigger_source)

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

        # Fast-path check: If syncing missing-only, check if this show actually needs cards or upgrades
        has_missing_cards = len(target_episodes) > 0
        has_interim_cards = any(src == "generator_interim" for src in existing_cards.values())

        if not force_all and not has_missing_cards and not has_interim_cards:
            logger.info(f"⚡ Fast-skip: All {len(episodes)} cards for '{show['title']}' are already up to date with no interim cards waiting. Skipping MediUX check.")
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
        synced_episodes_log = []

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
                synced_episodes_log.append({
                    "season_number": s_num,
                    "episode_number": e_num,
                    "title": ep["title"],
                    "source": "mediux",
                    "card_url": mediux_card_url
                })
            else:
                # Fallback: Render clean interim card using preset
                still_file = self.get_episode_backdrop_still(show, ep)
                if still_file:
                    season_style = get_effective_style(rating_key, s_num)
                    card_img = self.renderer.render(
                        base_image_path=still_file,
                        episode_title=ep["title"],
                        season_num=s_num,
                        episode_num=e_num,
                        style_config=season_style,
                        logo_image_path=self.get_show_logo_path(show)
                    )
                    if is_test:
                        show_test_dir = TEST_OUTPUT_DIR / clean_title
                        show_test_dir.mkdir(parents=True, exist_ok=True)
                        out_path = show_test_dir / f"S{s_num:02d}E{e_num:02d}_interim.jpg"
                        card_img.save(out_path, quality=95)
                        logger.info(f"🧪 [TEST MODE] Saved interim card to {out_path}")

                    card_bytes = None
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        card_img.save(tmp.name, quality=95)
                        self.plex.upload_episode_card(ep_key, tmp.name, force_live=force_live)
                        try:
                            card_bytes = Path(tmp.name).read_bytes()
                        except Exception:
                            pass
                        Path(tmp.name).unlink(missing_ok=True)

                    self._update_episode_card_status(ep_key, "generator_interim")
                    updated_count += 1
                    synced_episodes_log.append({
                        "season_number": s_num,
                        "episode_number": e_num,
                        "title": ep["title"],
                        "source": "generator_interim",
                        "image_bytes": card_bytes
                    })

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

        self._dispatch_sync_notifications(show, synced_episodes_log, matched_set=matched_set, trigger_source=trigger_source)

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

    def sync_show(
        self,
        rating_key: str,
        force_all: bool = True,
        force_live: bool = False,
        source_mode: Optional[str] = None,
        trigger_source: str = "manual"
    ) -> Dict[str, Any]:
        """Apply cards for a show according to its mode and style (synchronous wrapper)."""
        final_result = None
        for event in self.sync_show_generator(rating_key, force_all=force_all, force_live=force_live, source_mode=source_mode, trigger_source=trigger_source):
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

    def sync_episode_card(
        self,
        rating_key: str,
        season_number: int,
        episode_number: int,
        force_live: bool = False,
        source: str = "auto",
        custom_style: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Render or download a title card for a single episode and upload it to Plex.
        Honors TEST_MODE: if TEST_MODE is active and force_live is False, saves to cache/test_output/.
        """
        show = get_show(rating_key)
        if not show:
            raise ValueError(f"Show with rating_key {rating_key} not found")

        # Tell real-time listener to ignore feedback events for this show
        try:
            from backend.plex_listener import plex_listener
            plex_listener.ignore_show(rating_key, duration=30.0)
        except Exception:
            pass

        episodes = self.plex.get_show_episodes(rating_key)
        target_ep = next((e for e in episodes if e.get("season_number") == season_number and e.get("episode_number") == episode_number), None)
        if not target_ep:
            raise ValueError(f"Episode S{season_number:02d}E{episode_number:02d} not found in Plex")

        # If show was ignored, update to active mode on live upload
        if show.get("mode") == "ignored" and force_live:
            has_mediux = bool(show.get("mediux_set_url")) or bool(
                self.mediux.get_show_sets(show.get("tmdb_id")) if show.get("tmdb_id") else False
            )
            new_mode = "auto" if has_mediux else "generator_only"
            update_show_mode(rating_key, new_mode, show.get("mediux_set_url"))
            logger.info(f"Show '{show['title']}' was 'ignored'; updated to '{new_mode}' on single episode apply.")

        ep_key = target_ep["rating_key"]
        is_test = TEST_MODE and not force_live
        clean_title = "".join(c for c in show["title"] if c.isalnum() or c in (" ", "-", "_")).strip()
        clean_ep_title = "".join(c for c in target_ep["title"] if c.isalnum() or c in (" ", "-", "_")).strip()

        # Check if source is explicitly MediUX or Auto with an available MediUX card
        mediux_card_url = None
        if source in ("auto", "mediux") and show.get("mode") != "generator_only":
            tmdb_id = show.get("tmdb_id")
            if tmdb_id:
                all_sets = self.mediux.get_show_sets(tmdb_id)
                matched_set = None
                if show.get("mediux_set_url"):
                    target = str(show["mediux_set_url"]).strip()
                    for s in all_sets:
                        if s.get("set_url") == target or s.get("id") == target or f"/sets/{s.get('id')}" in target:
                            matched_set = s
                            break
                if not matched_set and all_sets:
                    matched_set = all_sets[0]

                if matched_set:
                    cards = matched_set.get("title_cards", {})
                    card_key = f"{season_number}_{episode_number}"
                    mediux_card_url = cards.get(card_key)

        # Upload MediUX card if requested and available
        if source == "mediux" or (source == "auto" and mediux_card_url):
            if not mediux_card_url:
                raise ValueError(f"No MediUX title card available for S{season_number:02d}E{episode_number:02d}")

            if is_test:
                show_test_dir = TEST_OUTPUT_DIR / clean_title
                show_test_dir.mkdir(parents=True, exist_ok=True)
                out_path = show_test_dir / f"S{season_number:02d}E{episode_number:02d}_mediux.jpg"
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

            try:
                from backend.discord_notifier import discord_notifier
                creator = matched_set.get("creator") if 'matched_set' in locals() and matched_set else None
                set_url = matched_set.get("set_url") if 'matched_set' in locals() and matched_set else None
                discord_notifier.notify_episode_card(
                    show_title=show["title"],
                    season_number=season_number,
                    episode_number=episode_number,
                    episode_title=target_ep["title"],
                    source="mediux",
                    card_image_path_or_url=mediux_card_url,
                    creator=creator,
                    set_url=set_url,
                    library_name=show.get("library_name"),
                    is_manual=True,
                    is_test=is_test
                )
            except Exception as e:
                logger.warning(f"Failed to dispatch Discord notification: {e}")

            return {
                "status": "success",
                "test_mode": is_test,
                "force_live": force_live,
                "season_number": season_number,
                "episode_number": episode_number,
                "title": target_ep["title"],
                "source": "mediux",
                "message": f"🧪 Test Mode: Saved MediUX card locally to cache/test_output/" if is_test else f"Successfully updated S{season_number:02d}E{episode_number:02d} with MediUX card in Plex!"
            }

        # Otherwise render using Generator
        style_to_use = get_effective_style(rating_key, season_number)
        if custom_style:
            style_to_use.update(custom_style)

        still_file = self.get_episode_backdrop_still(show, target_ep)
        if not still_file:
            raise ValueError(f"Could not obtain background still for S{season_number:02d}E{episode_number:02d}")

        card_img = self.renderer.render(
            base_image_path=still_file,
            episode_title=target_ep["title"],
            season_num=season_number,
            episode_num=episode_number,
            style_config=style_to_use,
            logo_image_path=self.get_show_logo_path(show)
        )

        if is_test:
            show_test_dir = TEST_OUTPUT_DIR / clean_title
            show_test_dir.mkdir(parents=True, exist_ok=True)
            out_path = show_test_dir / f"S{season_number:02d}E{episode_number:02d}_{clean_ep_title[:30]}.jpg"
            card_img.save(out_path, quality=95)
            logger.info(f"🧪 [TEST MODE] Saved generated card to {out_path}")

        card_bytes = None
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            card_img.save(tmp.name, quality=95)
            self.plex.upload_episode_card(ep_key, tmp.name, force_live=force_live)
            try:
                card_bytes = Path(tmp.name).read_bytes()
            except Exception:
                pass
            Path(tmp.name).unlink(missing_ok=True)

        card_status = "generator_preset" if show.get("mode") == "generator_only" else "generator_interim"
        self._update_episode_card_status(ep_key, card_status)

        try:
            from backend.discord_notifier import discord_notifier
            discord_notifier.notify_episode_card(
                show_title=show["title"],
                season_number=season_number,
                episode_number=episode_number,
                episode_title=target_ep["title"],
                source=card_status,
                card_image_bytes=card_bytes,
                library_name=show.get("library_name"),
                is_manual=True,
                is_test=is_test
            )
        except Exception as e:
            logger.warning(f"Failed to dispatch Discord notification: {e}")

        return {
            "status": "success",
            "test_mode": is_test,
            "force_live": force_live,
            "season_number": season_number,
            "episode_number": episode_number,
            "title": target_ep["title"],
            "source": card_status,
            "message": f"🧪 Test Mode: Generated card saved locally to cache/test_output/" if is_test else f"Successfully updated S{season_number:02d}E{episode_number:02d} in Plex!"
        }

    def revert_episode_card(
        self,
        show_rating_key: str,
        season_number: int,
        episode_number: int,
        force_live: bool = False
    ) -> Dict[str, Any]:
        """
        Revert an episode card back to Plex's native video frame / auto-generated thumbnail.
        Clears local still overrides, deletes the uploaded poster from Plex, unlocks the thumb,
        and sets local card_source to 'plex_native'.
        """
        from backend.db import delete_episode_still_override
        # 1. Ignore events on listener during revert
        try:
            from backend.plex_listener import plex_listener
            plex_listener.ignore_show(show_rating_key, duration=30.0)
        except Exception:
            pass

        # 2. Delete any custom screencap override
        delete_episode_still_override(str(show_rating_key), season_number, episode_number)

        # 3. Locate episode record in DB
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rating_key, card_url FROM episodes
            WHERE show_rating_key = ? AND season_number = ? AND episode_number = ?
        """, (str(show_rating_key), season_number, episode_number))
        row = cursor.fetchone()

        ep_key = str(row["rating_key"]) if row else None

        # 4. If not found in DB, try fetching from Plex directly
        if not ep_key:
            try:
                episodes = self.plex.get_show_episodes(str(show_rating_key))
                target = next((e for e in episodes if e.get("season_number") == season_number and e.get("episode_number") == episode_number), None)
                if target:
                    ep_key = str(target["rating_key"])
            except Exception:
                pass

        # 5. Tell Plex to delete the uploaded poster and unlock the thumb
        if ep_key:
            try:
                self.plex.revert_episode_card(ep_key, force_live=force_live)
            except Exception as e:
                logger.warning(f"Failed to revert episode card in Plex for ep {ep_key}: {e}")

        # 6. Fetch Plex's native thumbUrl
        plex_thumb = None
        if ep_key:
            try:
                ep_item = self.plex.server.fetchItem(int(ep_key))
                plex_thumb = ep_item.thumbUrl if hasattr(ep_item, "thumbUrl") else None
            except Exception:
                pass

        # 7. Update local DB
        cursor.execute("""
            UPDATE episodes
            SET card_url = ?, card_source = 'plex_native', updated_at = CURRENT_TIMESTAMP
            WHERE show_rating_key = ? AND season_number = ? AND episode_number = ?
        """, (plex_thumb, str(show_rating_key), season_number, episode_number))
        conn.commit()
        conn.close()

        # Invalidate preview cache
        from backend.config import PREVIEWS_DIR
        for p in PREVIEWS_DIR.glob(f"*{show_rating_key}*"):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

        return {
            "status": "success",
            "show_rating_key": str(show_rating_key),
            "season_number": season_number,
            "episode_number": episode_number,
            "card_source": "plex_native",
            "card_url": plex_thumb,
            "message": f"Successfully reverted S{season_number:02d}E{episode_number:02d} to Plex default video frame."
        }

    def revert_show_cards(self, show_rating_key: str, force_live: bool = False) -> Dict[str, Any]:
        """Revert all episodes of a show back to Plex native video frames."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT season_number, episode_number FROM episodes
            WHERE show_rating_key = ?
            ORDER BY season_number ASC, episode_number ASC
        """, (str(show_rating_key),))
        episodes = [dict(r) for r in cursor.fetchall()]
        conn.close()

        reverted_count = 0
        for ep in episodes:
            try:
                self.revert_episode_card(
                    show_rating_key=show_rating_key,
                    season_number=ep["season_number"],
                    episode_number=ep["episode_number"],
                    force_live=force_live
                )
                reverted_count += 1
            except Exception as e:
                logger.warning(f"Failed to revert card for S{ep['season_number']}E{ep['episode_number']}: {e}")

        return {
            "status": "success",
            "show_rating_key": str(show_rating_key),
            "reverted_count": reverted_count,
            "message": f"Successfully reverted {reverted_count} episode cards to Plex default video frames."
        }
