import logging
import base64
import io
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend import config
from backend.config import BASE_DIR, HOST, PORT, CUSTOM_FONTS_DIR, POSTERS_DIR
from backend.db import (
    init_db, get_all_shows, get_show, update_show_mode, update_show_style,
    get_setting, set_setting, get_all_settings, bulk_update_show_modes,
    update_show_tmdb_id
)
from backend.sync_manager import SyncManager
from backend.ai_styler import AIStyler
from backend.tmdb_client import TMDbClient
from backend.mediux_client import MediuxClient
from backend.generator.renderer import TitleCardRenderer
from backend.scheduler import start_scheduler
from backend.plex_listener import plex_listener
from backend.auth import (
    PlexOAuth, SESSION_COOKIE_NAME, SESSION_DURATION_DAYS,
    create_session_token, verify_session_token
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="PlexCards", version="0.8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Intercept requests to protect /api/ routes when ENABLE_AUTH is active."""
    path = request.url.path
    if config.ENABLE_AUTH and path.startswith("/api/") and not path.startswith("/api/auth") and path != "/api/config" and "/poster" not in path:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]

        user = verify_session_token(token) if token else None
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        request.state.user = user

    return await call_next(request)

# Initialize subsystems
init_db()
sync_mgr = SyncManager()
ai_styler = AIStyler()
tmdb = TMDbClient()
tvdb = sync_mgr.tvdb
mediux = MediuxClient()
renderer = TitleCardRenderer()

@app.on_event("startup")
def on_startup():
    start_scheduler()
    plex_listener.start()
    import threading
    threading.Thread(target=sync_mgr.sync_show_statuses, daemon=True).start()
    logger.info("PlexCards API and Live AlertListener started.")

@app.on_event("shutdown")
def on_shutdown():
    plex_listener.stop()
    logger.info("PlexCards API and Live AlertListener stopped.")

# ----------------------------------------------------
# API ENDPOINTS
# ----------------------------------------------------

@app.get("/api/config")
def get_config_info():
    """Return app settings including TEST_MODE, listener status, and auth flag."""
    from backend.config import TEST_MODE, PLEX_TV_LIBRARY, POLL_INTERVAL_HOURS
    return {
        "version": "0.8.0",
        "test_mode": TEST_MODE,
        "tv_library": PLEX_TV_LIBRARY,
        "poll_interval_hours": POLL_INTERVAL_HOURS,
        "listener_connected": plex_listener.is_connected,
        "auth_enabled": config.ENABLE_AUTH,
        "has_gemini_key": bool(ai_styler.api_key),
        "has_tvdb_key": bool(tvdb.is_configured),
        "has_tmdb_key": bool(tmdb.api_key)
    }

# ----------------------------------------------------
# AUTH ENDPOINTS
# ----------------------------------------------------

@app.get("/api/auth/status")
def get_auth_status(request: Request):
    """Return whether authentication is enabled and current user info if logged in."""
    if not config.ENABLE_AUTH:
        return {
            "auth_enabled": False,
            "authenticated": True,
            "user": {"username": "admin", "thumb": None}
        }
    
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            
    user = verify_session_token(token) if token else None
    if user:
        return {
            "auth_enabled": True,
            "authenticated": True,
            "user": {
                "username": user.get("username"),
                "email": user.get("email"),
                "thumb": user.get("thumb")
            }
        }
    return {
        "auth_enabled": True,
        "authenticated": False,
        "user": None
    }

@app.post("/api/auth/pin")
def create_auth_pin():
    """Generate a Plex OAuth PIN and authorization URL."""
    if not config.ENABLE_AUTH:
        return {"error": "Authentication is disabled"}
    try:
        return PlexOAuth.create_pin()
    except Exception as e:
        logger.error(f"Failed to create Plex OAuth PIN: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create Plex PIN: {e}")

@app.get("/api/auth/poll")
def poll_auth_pin(pin_id: int, response: Response):
    """Poll Plex PIN status, verify user credentials, and issue session cookie if approved."""
    if not config.ENABLE_AUTH:
        return {"status": "authenticated"}
        
    try:
        auth_token = PlexOAuth.poll_pin(pin_id)
        if not auth_token:
            return {"status": "pending"}
            
        machine_id = None
        try:
            machine_id = sync_mgr.plex.server.machineIdentifier
        except Exception as e:
            logger.debug(f"Could not get server machine identifier: {e}")
            
        allowed, plex_user, msg = PlexOAuth.verify_access(auth_token, server_machine_id=machine_id)
        if not allowed:
            logger.warning(f"Access denied during Plex auth: {msg}")
            return {"status": "denied", "detail": msg}
            
        user_data = {
            "username": (plex_user or {}).get("username", "Unknown"),
            "email": (plex_user or {}).get("email"),
            "thumb": (plex_user or {}).get("thumb"),
            "id": (plex_user or {}).get("id")
        }
        token = create_session_token(user_data)
        
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=SESSION_DURATION_DAYS * 86400,
            httponly=True,
            samesite="lax",
            secure=False
        )
        
        return {
            "status": "authenticated",
            "token": token,
            "user": user_data
        }
    except Exception as e:
        logger.error(f"Error polling Plex PIN: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/logout")
def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "logged_out"}

@app.get("/api/listener/status")
def get_listener_status():
    """Return the current status of the real-time Plex WebSocket alert listener."""
    return {
        "connected": plex_listener.is_connected,
        "tv_section_id": plex_listener._tv_section_id
    }

@app.get("/api/fonts")
def list_fonts():
    """List all available local, custom, and cached fonts."""
    fonts = renderer.get_available_fonts()
    return {"fonts": fonts}

@app.post("/api/fonts/upload")
async def upload_custom_font(file: UploadFile = File(...)):
    """Upload a custom .ttf or .otf font file."""
    if not (file.filename.endswith(".ttf") or file.filename.endswith(".otf")):
        raise HTTPException(status_code=400, detail="Only .ttf and .otf font files are supported")

    dest = CUSTOM_FONTS_DIR / file.filename
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    logger.info(f"✓ Saved uploaded custom font to {dest}")
    return {"status": "success", "font_name": dest.stem, "filename": file.filename}

@app.get("/api/shows")
def list_shows():
    """List all indexed TV shows with status and card statistics."""
    shows = get_all_shows()
    for s in shows:
        if s.get("poster_url"):
            s["poster_url"] = f"/api/shows/{s['rating_key']}/poster.jpg"
    return {"shows": shows}

@app.get("/api/shows/{rating_key}/poster")
@app.get("/api/shows/{rating_key}/poster.jpg")
def get_show_poster(rating_key: str, request: Request):
    """Serve optimized, compressed show poster with local disk caching and Cloudflare-friendly headers."""
    from fastapi.responses import FileResponse, Response
    from PIL import Image
    import requests

    poster_path = POSTERS_DIR / f"{rating_key}.jpg"
    headers = {
        "Cache-Control": "public, max-age=604800, stale-while-revalidate=86400",
        "ETag": f'"{rating_key}"'
    }

    if poster_path.exists():
        if request.headers.get("if-none-match") == f'"{rating_key}"':
            return Response(status_code=304, headers=headers)
        return FileResponse(
            poster_path,
            media_type="image/jpeg",
            headers=headers
        )

    show = get_show(rating_key)
    target_url = show.get("poster_url") if show else None

    # If no URL stored, try fetching directly from Plex item
    if not target_url and sync_mgr.plex:
        try:
            item = sync_mgr.plex.server.fetchItem(int(rating_key))
            target_url = item.posterUrl if hasattr(item, "posterUrl") else None
        except Exception:
            pass

    # If still no URL, try TMDb
    if not target_url and show and show.get("tmdb_id"):
        try:
            details = tmdb.get_show_details(show["tmdb_id"])
            target_url = details.get("poster_url")
        except Exception:
            pass

    if not target_url:
        raise HTTPException(status_code=404, detail="Poster not found")

    try:
        r = requests.get(target_url, timeout=10)
        if r.status_code == 200:
            # Resize to web-optimized thumbnail (max width 420px, ~40-60KB) to save 98% bandwidth on Cloudflare Tunnel
            try:
                with Image.open(io.BytesIO(r.content)) as im:
                    if im.width > 420:
                        new_h = int(im.height * (420.0 / im.width))
                        im = im.resize((420, new_h), Image.Resampling.LANCZOS)
                    im.convert("RGB").save(poster_path, format="JPEG", quality=82, optimize=True)
            except Exception as resize_err:
                logger.warning(f"Could not resize poster image: {resize_err}, saving raw.")
                with open(poster_path, "wb") as f:
                    f.write(r.content)

            return FileResponse(
                poster_path,
                media_type="image/jpeg",
                headers=headers
            )
        else:
            logger.warning(f"Failed to fetch poster from {target_url}: HTTP {r.status_code}")
            raise HTTPException(status_code=r.status_code, detail="Could not fetch poster from origin")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching poster for show {rating_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch poster")

@app.post("/api/library/scan")
def scan_library():
    """Scan Plex server and index all shows."""
    count = sync_mgr.scan_and_index_library()
    return {"status": "success", "indexed_shows": count}

@app.get("/api/shows/{rating_key}")
def get_show_details(rating_key: str):
    """Get full details, episodes, style configuration, and available MediUX sets."""
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    if show.get("poster_url"):
        show["poster_url"] = f"/api/shows/{rating_key}/poster"

    # Auto-backfill tvdb_id from Plex or TMDb if missing
    if not show.get("tvdb_id") and tvdb.is_configured:
        try:
            plex_item = sync_mgr.plex.server.fetchItem(int(rating_key))
            found_tvdb = sync_mgr.plex._extract_tvdb_id(plex_item)
            if not found_tvdb and show.get("tmdb_id"):
                found_tvdb = tvdb.resolve_tvdb_id_from_remote(str(show["tmdb_id"]))
            if found_tvdb:
                from backend.db import update_show_tvdb_id
                update_show_tvdb_id(rating_key, found_tvdb)
                show["tvdb_id"] = found_tvdb
        except Exception:
            pass

    # Refresh show broadcast status from TVDB if TVDB is prioritized
    priority = get_setting("metadata_provider_priority", "tvdb").lower()
    if show.get("tvdb_id") and priority == "tvdb" and tvdb.is_configured:
        try:
            tvdb_status = tvdb.get_series_status(int(show["tvdb_id"]))
            if tvdb_status and tvdb_status != show.get("status"):
                from backend.db import update_show_status
                update_show_status(rating_key, tvdb_status)
                show["status"] = tvdb_status
        except Exception:
            pass

    episodes = sync_mgr.plex.get_show_episodes(rating_key)
    tmdb_id = show.get("tmdb_id")

    # Fetch MediUX sets for this show
    pref_str = get_setting("preferred_mediux_creators", "")
    preferred_creators = [p.strip() for p in pref_str.split(",") if p.strip()]

    available_sets = []
    auto_mediux_set_id = None
    if tmdb_id:
        try:
            available_sets = mediux.get_show_sets(tmdb_id)
            required_seasons = list(set(ep["season_number"] for ep in episodes))
            auto_set = mediux.find_best_matching_set(tmdb_id, required_seasons, preferred_creators=preferred_creators)
            if auto_set:
                auto_mediux_set_id = auto_set.get("id")
        except Exception as e:
            logger.warning(f"Could not load MediUX sets: {e}")

    # Fetch TMDb show info (genres, overview) with Plex fallback
    tmdb_info = None
    if tmdb_id:
        tmdb_info = tmdb.get_show_details(tmdb_id)
    if not tmdb_info:
        tmdb_info = {}
    if not tmdb_info.get("genres") or not tmdb_info.get("overview"):
        try:
            plex_item = sync_mgr.plex.server.fetchItem(int(rating_key))
            if not tmdb_info.get("genres") and hasattr(plex_item, "genres"):
                tmdb_info["genres"] = [g.tag for g in plex_item.genres]
            if not tmdb_info.get("overview") and hasattr(plex_item, "summary"):
                tmdb_info["overview"] = plex_item.summary
        except Exception:
            pass

    # Request 2: If style doesn't exist yet, check auto_gemini setting before querying Gemini
    auto_gemini = get_setting("auto_gemini_suggestion", "true").lower() == "true"
    initial_ai_generated = False
    ai_error = None
    if auto_gemini and not show.get("has_custom_style") and tmdb_info and ai_styler.api_key:
        try:
            logger.info(f"✨ Generating initial AI style suggestion for '{show['title']}'...")
            poster_path = POSTERS_DIR / f"{rating_key}.jpg"
            first_ep = episodes[0] if episodes else {"season_number": 1, "episode_number": 1, "title": ""}
            still_path = sync_mgr.get_episode_backdrop_still(show, first_ep)
            ai_style = ai_styler.suggest_style(
                show_title=show["title"],
                genres=tmdb_info.get("genres", []),
                overview=tmdb_info.get("overview", ""),
                poster_path=poster_path if poster_path.exists() else None,
                still_path=still_path if (still_path and still_path.exists()) else None
            )
            if ai_style.get("error"):
                ai_error = ai_style["error"]
                logger.warning(f"Could not auto-generate AI style for show {show['title']}: {ai_error}")
            else:
                update_show_style(rating_key, {**ai_style, "has_custom_style": 1})
                show = get_show(rating_key)
                initial_ai_generated = True
        except Exception as e:
            ai_error = str(e)
            logger.warning(f"Could not auto-generate AI style for show {show['title']}: {e}")

    return {
        "show": show,
        "episodes": episodes,
        "available_sets": available_sets,
        "auto_mediux_set_id": auto_mediux_set_id,
        "preferred_creators": preferred_creators,
        "tmdb_info": tmdb_info,
        "initial_ai_generated": initial_ai_generated,
        "ai_error": ai_error,
        "has_gemini_key": bool(ai_styler.api_key)
    }

@app.get("/api/settings")
def list_settings():
    """Get global application settings."""
    return {"settings": get_all_settings()}

@app.post("/api/settings")
def update_settings(payload: dict = Body(...)):
    """Update global application settings."""
    for k, v in payload.items():
        set_setting(k, str(v))
    return {"status": "success", "settings": get_all_settings()}

@app.get("/api/settings/default-style")
def get_default_style_endpoint():
    """Get the current default title card generator style and a sample show for live preview."""
    from backend.db import get_default_generator_style, get_db
    style = get_default_generator_style()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT rating_key, title, year, tmdb_id, backdrop_url FROM shows ORDER BY title ASC LIMIT 1")
    row = cursor.fetchone()
    sample_show = None
    sample_episode = None
    if row:
        sample_show = dict(row)
        cursor.execute(
            "SELECT season_number, episode_number, title FROM episodes WHERE show_rating_key = ? ORDER BY season_number ASC, episode_number ASC LIMIT 1",
            (sample_show["rating_key"],)
        )
        ep_row = cursor.fetchone()
        if ep_row:
            sample_episode = dict(ep_row)
        else:
            sample_episode = {"season_number": 1, "episode_number": 1, "title": "Pilot"}
    conn.close()

    return {
        "style": style,
        "sample_show": sample_show,
        "sample_episode": sample_episode
    }

@app.post("/api/settings/default-style")
def set_default_style_endpoint(payload: dict = Body(...)):
    """Save the user-configured default generator style."""
    from backend.db import set_default_generator_style
    saved = set_default_generator_style(payload)
    return {"status": "success", "style": saved}

@app.post("/api/shows/bulk-mode")
def bulk_set_show_mode(payload: dict = Body(...)):
    """Bulk update the mode of all shows (e.g. to 'ignored')."""
    mode = payload.get("mode", "ignored")
    count = bulk_update_show_modes(mode)
    return {"status": "success", "updated_count": count, "mode": mode}

@app.post("/api/shows/{rating_key}/mode")
def set_show_mode(rating_key: str, payload: dict = Body(...)):
    """Update show mode ('auto', 'generator_only', 'mediux_locked', 'ignored') and set URL."""
    mode = payload.get("mode", "auto")
    mediux_set_url = payload.get("mediux_set_url")
    update_show_mode(rating_key, mode, mediux_set_url)
    return {"status": "success", "mode": mode, "mediux_set_url": mediux_set_url}

@app.get("/api/tmdb/search")
def search_tmdb(query: str, year: Optional[int] = None):
    """Search TMDb for TV shows matching the query."""
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    results = tmdb.search_shows(query, year=year)
    return {"results": results}

@app.post("/api/shows/{rating_key}/tmdb-match")
def match_show_tmdb(rating_key: str, payload: dict = Body(...)):
    """Link a show to a TMDb ID and backfill poster/backdrop from TMDb if available."""
    tmdb_id = payload.get("tmdb_id")
    if not tmdb_id:
        raise HTTPException(status_code=400, detail="tmdb_id is required")

    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    try:
        tmdb_id = int(tmdb_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid tmdb_id format")

    details = tmdb.get_show_details(tmdb_id)
    poster_url = None
    backdrop_url = None
    if details:
        poster_url = details.get("poster_url")
        backdrop_url = details.get("backdrop_url")

    # Invalidate cached poster if TMDb match updated
    cached_poster = POSTERS_DIR / f"{rating_key}.jpg"
    if cached_poster.exists():
        try:
            cached_poster.unlink(missing_ok=True)
        except Exception:
            pass

    show_status = details.get("status") if details else None
    update_show_tmdb_id(rating_key, tmdb_id, poster_url=poster_url, backdrop_url=backdrop_url, status=show_status)
    updated_show = get_show(rating_key)
    if updated_show and updated_show.get("poster_url"):
        updated_show["poster_url"] = f"/api/shows/{rating_key}/poster"
    return {"status": "success", "show": updated_show, "tmdb_info": details}

@app.get("/api/tvdb/search")
def search_tvdb(query: str, year: Optional[int] = None):
    """Search TheTVDB for TV shows matching the query."""
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    if not tvdb.is_configured:
        raise HTTPException(status_code=400, detail="TheTVDB API is not configured in .env")
    results = tvdb.search_shows(query, year=year)
    return {"results": results}

@app.post("/api/shows/{rating_key}/tvdb-match")
def match_show_tvdb(rating_key: str, payload: dict = Body(...)):
    """Link a show to a TheTVDB ID and auto-resolve TMDb ID if available."""
    from backend.db import update_show_tvdb_id, update_show_tmdb_id
    tvdb_id = payload.get("tvdb_id")
    if not tvdb_id:
        raise HTTPException(status_code=400, detail="tvdb_id is required")

    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    try:
        tvdb_id = int(tvdb_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid tvdb_id format")

    series_data = tvdb.get_series_extended(tvdb_id)
    resolved_tmdb = tvdb.resolve_tmdb_id(tvdb_id)

    update_show_tvdb_id(rating_key, tvdb_id)
    if resolved_tmdb and not show.get("tmdb_id"):
        update_show_tmdb_id(rating_key, resolved_tmdb)

    updated_show = get_show(rating_key)
    if updated_show and updated_show.get("poster_url"):
        updated_show["poster_url"] = f"/api/shows/{rating_key}/poster"

    return {
        "status": "success",
        "show": updated_show,
        "tvdb_info": series_data,
        "resolved_tmdb_id": resolved_tmdb
    }

@app.post("/api/shows/{rating_key}/plex-fix-match")
def fix_match_in_plex(rating_key: str, payload: dict = Body(default={})):
    """Instruct Plex server to execute fixMatch on the show."""
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    title = payload.get("title") or show.get("title")
    year = payload.get("year") or show.get("year")

    try:
        res = sync_mgr.plex.fix_match_show(rating_key, title=title, year=year)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("message", "Fix match failed"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering Plex fixMatch for {rating_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/shows/{rating_key}/style")
def save_show_style(rating_key: str, payload: dict = Body(...)):
    """Save generator style preset and options."""
    if "subheading_font_family" in payload:
        s_ff = (payload.get("subheading_font_family") or "").strip()
        payload["subheading_font_family"] = s_ff if s_ff else None
    update_show_style(rating_key, {**payload, "has_custom_style": 1})
    return {"status": "success"}

@app.post("/api/shows/{rating_key}/preview")
def generate_preview(rating_key: str, payload: dict = Body(...)):
    """Generate a live preview of the title card with disk-based caching."""
    import hashlib
    import json
    from fastapi.responses import FileResponse
    from backend.config import PREVIEWS_DIR

    show = get_show(rating_key)
    if not show:
        if rating_key == "default":
            show = {
                "rating_key": "default",
                "title": "Sample Show",
                "tmdb_id": None
            }
        else:
            raise HTTPException(status_code=404, detail="Show not found")

    tmdb_id = show.get("tmdb_id")
    season_num = payload.get("season_number", 1)
    episode_num = payload.get("episode_number", 1)
    episode_title = payload.get("episode_title", "Sample Episode Title")

    style = {**show, **payload}
    if "subheading_font_family" in payload:
        s_ff = (payload.get("subheading_font_family") or "").strip()
        style["subheading_font_family"] = s_ff if s_ff else None

    from backend.db import get_episode_still_override
    still_override = get_episode_still_override(rating_key, season_num, episode_num)

    # Request 5: Compute hash and check preview cache for instantaneous load
    cache_key = hashlib.md5(json.dumps({
        "rk": rating_key,
        "s": season_num,
        "e": episode_num,
        "t": episode_title,
        "still": still_override or "",
        "pos": style.get("text_position"),
        "font": style.get("font_family"),
        "s_font": style.get("subheading_font_family"),
        "c": style.get("font_color"),
        "sc": style.get("subheading_color"),
        "icon": style.get("subheading_icon"),
        "gw": style.get("gradient_width_pct"),
        "go": style.get("gradient_opacity_pct"),
        "sub": style.get("show_subheading"),
        "sub_fmt": style.get("subheading_format"),
        "tfs": style.get("title_font_size", 108),
        "sfs": style.get("subheading_font_size", 52),
        "tbw": style.get("text_box_width_pct", 46),
        "sg": style.get("subheading_gap", 16),
        "s_case": style.get("subheading_casing", "upper"),
        "s_pos": style.get("subheading_position", "above"),
        "s_track": style.get("subheading_tracking", 0),
        "blur": style.get("frosted_blur_pct", 0),
        "grain": style.get("film_grain_pct", 0),
        "vig": style.get("vignette_pct", 0),
        "shd": style.get("text_shadow_mode", "subtle"),
        "logo": style.get("show_logo", 0),
        "l_pos": style.get("logo_position", "top_right"),
        "l_op": style.get("logo_opacity_pct", 80),
        "l_mono": style.get("logo_monochrome", 1)
    }, sort_keys=True).encode()).hexdigest()

    cached_preview = PREVIEWS_DIR / f"{cache_key}.jpg"
    if cached_preview.exists():
        return FileResponse(cached_preview, media_type="image/jpeg")

    # Fetch still with fallback cascade
    ep_dict = {
        "season_number": season_num,
        "episode_number": episode_num,
        "title": episode_title
    }
    try:
        episodes = sync_mgr.plex.get_show_episodes(rating_key)
        for ep in episodes:
            if ep["season_number"] == season_num and ep["episode_number"] == episode_num:
                ep_dict = ep
                break
    except Exception:
        pass

    still_path = sync_mgr.get_episode_backdrop_still(show, ep_dict)
    if not still_path:
        raise HTTPException(status_code=404, detail="Could not fetch or generate still image for preview")

    logo_path = sync_mgr.get_show_logo_path(show)

    card_img = renderer.render(
        base_image_path=still_path,
        episode_title=episode_title,
        season_num=season_num,
        episode_num=episode_num,
        style_config=style,
        logo_image_path=logo_path
    )

    card_img.save(cached_preview, format="JPEG", quality=92)
    return FileResponse(cached_preview, media_type="image/jpeg")

@app.get("/api/shows/{rating_key}/raw-still")
def get_raw_still(rating_key: str, season_number: int = 1, episode_number: int = 1):
    """Return the raw episode still image for before/after comparison slider."""
    from fastapi.responses import FileResponse
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    ep_dict = {"season_number": season_number, "episode_number": episode_number, "title": ""}
    try:
        episodes = sync_mgr.plex.get_show_episodes(rating_key)
        for ep in episodes:
            if ep["season_number"] == season_number and ep["episode_number"] == episode_number:
                ep_dict = ep
                break
    except Exception:
        pass
    still_path = sync_mgr.get_episode_backdrop_still(show, ep_dict)
    if not still_path or not still_path.exists():
        raise HTTPException(status_code=404, detail="Still image not found")
    return FileResponse(still_path, media_type="image/jpeg")

@app.get("/api/shows/{rating_key}/logo")
def get_show_logo(rating_key: str):
    """Return the transparent PNG logo for a show if available."""
    from fastapi.responses import FileResponse
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    logo_path = sync_mgr.get_show_logo_path(show)
    if not logo_path or not logo_path.exists():
        raise HTTPException(status_code=404, detail="Logo not available for this show")
    return FileResponse(logo_path, media_type="image/png")

@app.get("/api/shows/{rating_key}/episodes/{season_number}/{episode_number}/stills")
def get_episode_stills(rating_key: str, season_number: int, episode_number: int):
    """Retrieve all candidate backdrop stills for an episode from TVDB and TMDb."""
    from backend.db import get_episode_still_override, get_setting
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    priority = get_setting("metadata_provider_priority", "tvdb").lower()
    tvdb_stills = []
    tmdb_stills = []

    # Auto-backfill tvdb_id if missing
    if not show.get("tvdb_id") and tvdb.is_configured:
        try:
            plex_item = sync_mgr.plex.server.fetchItem(int(rating_key))
            found_tvdb = sync_mgr.plex._extract_tvdb_id(plex_item)
            if not found_tvdb and show.get("tmdb_id"):
                found_tvdb = tvdb.resolve_tvdb_id_from_remote(str(show["tmdb_id"]))
            if found_tvdb:
                from backend.db import update_show_tvdb_id
                update_show_tvdb_id(rating_key, found_tvdb)
                show["tvdb_id"] = found_tvdb
        except Exception:
            pass

    if show.get("tvdb_id") and tvdb.is_configured:
        try:
            tvdb_stills = tvdb.get_episode_stills_list(int(show["tvdb_id"]), season_number, episode_number)
        except Exception as e:
            logger.warning(f"Error fetching TVDB stills for {rating_key}: {e}")

    if show.get("tmdb_id") and tmdb.api_key:
        try:
            tmdb_stills = tmdb.get_episode_stills_list(int(show["tmdb_id"]), season_number, episode_number)
            for s in tmdb_stills:
                s["provider"] = "tmdb"
        except Exception as e:
            logger.warning(f"Error fetching TMDb stills for {rating_key}: {e}")

    # Combine according to priority
    if priority == "tvdb":
        stills = tvdb_stills + tmdb_stills
    else:
        stills = tmdb_stills + tvdb_stills

    override = get_episode_still_override(rating_key, season_number, episode_number)

    for s in stills:
        if override:
            s["is_selected"] = (s["file_path"] == override)
        else:
            s["is_selected"] = s.get("is_top_pick", False)

    return {
        "stills": stills,
        "selected_still_path": override or (stills[0]["file_path"] if stills else None)
    }

@app.post("/api/shows/{rating_key}/episodes/{season_number}/{episode_number}/select-still")
def select_episode_still(rating_key: str, season_number: int, episode_number: int, payload: dict = Body(...)):
    """Save user-selected still frame override for an episode and pre-cache it."""
    from backend.db import set_episode_still_override
    still_path = payload.get("still_path")
    if not still_path:
        raise HTTPException(status_code=400, detail="still_path is required")

    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    # Persist override in SQLite
    set_episode_still_override(rating_key, season_number, episode_number, still_path)

    # Pre-download specific still file in background
    cached_path = None
    if (still_path.startswith("http://") or still_path.startswith("https://")) and show.get("tvdb_id"):
        cached_path = tvdb.get_episode_still(int(show["tvdb_id"]), season_number, episode_number, specific_still_url=still_path)
    elif show.get("tmdb_id"):
        cached_path = tmdb.get_episode_still(int(show["tmdb_id"]), season_number, episode_number, specific_still_path=still_path)

    return {
        "status": "success",
        "still_path": still_path,
        "season_number": season_number,
        "episode_number": episode_number,
        "cached": bool(cached_path and cached_path.exists())
    }

@app.post("/api/shows/{rating_key}/auto-pick-stills")
def auto_pick_stills(rating_key: str, payload: dict = Body(default={})):
    """Auto-select the highest quality still for all episodes of a show or season respecting provider priority."""
    from backend.db import set_episode_still_override, get_setting
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    target_season = payload.get("season_number")
    priority = get_setting("metadata_provider_priority", "tvdb").lower()
    episodes = sync_mgr.plex.get_show_episodes(rating_key)
    updated_count = 0

    for ep in episodes:
        s_num = ep["season_number"]
        e_num = ep["episode_number"]
        if target_season is not None and s_num != target_season:
            continue

        best = None
        if priority == "tvdb" and show.get("tvdb_id") and tvdb.is_configured:
            stills = tvdb.get_episode_stills_list(int(show["tvdb_id"]), s_num, e_num)
            if stills:
                best = stills[0]["file_path"]
                tvdb.get_episode_still(int(show["tvdb_id"]), s_num, e_num, specific_still_url=best)

        if not best and show.get("tmdb_id") and tmdb.api_key:
            stills = tmdb.get_episode_stills_list(int(show["tmdb_id"]), s_num, e_num)
            if stills:
                best = stills[0]["file_path"]
                tmdb.get_episode_still(int(show["tmdb_id"]), s_num, e_num, specific_still_path=best)

        if best:
            set_episode_still_override(rating_key, s_num, e_num, best)
            updated_count += 1

    return {
        "status": "success",
        "updated_episodes": updated_count,
        "message": f"Smart auto-picked best quality stills for {updated_count} episodes."
    }

@app.get("/api/shows/{rating_key}/palette")
def get_still_palette(
    rating_key: str,
    season_number: Optional[int] = None,
    episode_number: Optional[int] = None
):
    """Extract dominant and vibrant color palette from current episode still or show backdrop."""
    from backend.generator.palette import extract_palette
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    ep_dict = {
        "season_number": season_number if season_number is not None else 1,
        "episode_number": episode_number if episode_number is not None else 1,
        "title": ""
    }
    still_path = sync_mgr.get_episode_backdrop_still(show, ep_dict)
    if not still_path or not still_path.exists():
        raise HTTPException(status_code=404, detail="Still image not available for palette extraction")

    palette = extract_palette(still_path)
    return palette

@app.post("/api/shows/{rating_key}/apply")
def apply_cards_to_show(rating_key: str, payload: dict = Body(default={})):
    """Download or generate cards and upload them to Plex for this show."""
    force_all = payload.get("force_all", True)
    force_live = payload.get("force_live", False)
    source_mode = payload.get("source_mode")
    res = sync_mgr.sync_show(rating_key, force_all=force_all, force_live=force_live, source_mode=source_mode)
    return res

@app.post("/api/shows/{rating_key}/apply-stream")
def apply_cards_to_show_stream(rating_key: str, payload: dict = Body(default={})):
    """Stream card application progress as Newline-Delimited JSON (NDJSON)."""
    import json
    force_all = payload.get("force_all", True)
    force_live = payload.get("force_live", False)
    source_mode = payload.get("source_mode")

    def event_stream():
        for event in sync_mgr.sync_show_generator(rating_key, force_all=force_all, force_live=force_live, source_mode=source_mode):
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

@app.post("/api/shows/{rating_key}/episodes/{season_number}/{episode_number}/apply")
def apply_card_to_episode(
    rating_key: str,
    season_number: int,
    episode_number: int,
    payload: dict = Body(default={})
):
    """Generate or download title card and upload directly to Plex for a single episode."""
    force_live = payload.get("force_live", False)
    source = payload.get("source", "auto")
    custom_style = payload.get("custom_style")
    try:
        res = sync_mgr.sync_episode_card(
            rating_key=rating_key,
            season_number=season_number,
            episode_number=episode_number,
            force_live=force_live,
            source=source,
            custom_style=custom_style
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to apply card to S{season_number}E{episode_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shows/{rating_key}/ai-style")
def ai_suggest_style(rating_key: str, payload: dict = Body(...)):
    """Use Gemini AI to analyze the show and suggest typography & colors."""
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    tmdb_id = show.get("tmdb_id")
    tmdb_info = tmdb.get_show_details(tmdb_id) if tmdb_id else {}
    if not tmdb_info:
        tmdb_info = {}
    
    genres = tmdb_info.get("genres", [])
    overview = tmdb_info.get("overview", "")
    if not genres or not overview:
        try:
            plex_item = sync_mgr.plex.server.fetchItem(int(rating_key))
            if not genres and hasattr(plex_item, "genres"):
                genres = [g.tag for g in plex_item.genres]
            if not overview and hasattr(plex_item, "summary"):
                overview = plex_item.summary
        except Exception:
            pass

    user_prompt = payload.get("prompt", "")
    poster_path = POSTERS_DIR / f"{rating_key}.jpg"

    # Fetch episode still for vision subject-aware analysis if available
    s_num = payload.get("season_number", 1)
    e_num = payload.get("episode_number", 1)
    still_path = sync_mgr.get_episode_backdrop_still(show, {"season_number": s_num, "episode_number": e_num, "title": ""})

    suggestion = ai_styler.suggest_style(
        show_title=show["title"],
        genres=genres,
        overview=overview,
        user_prompt=user_prompt,
        poster_path=poster_path if poster_path.exists() else None,
        still_path=still_path if (still_path and still_path.exists()) else None
    )
    if suggestion.get("error"):
        status_code = 503 if suggestion.get("is_unavailable") else 500
        raise HTTPException(status_code=status_code, detail=suggestion["error"])

    return suggestion

# Mount built React frontend if dist exists, otherwise fallback to frontend dir
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    frontend_dir = BASE_DIR / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
