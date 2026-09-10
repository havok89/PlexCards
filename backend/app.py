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
from backend.config import BASE_DIR, HOST, PORT, CUSTOM_FONTS_DIR
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

app = FastAPI(title="PlexPosters", version="1.0.0")

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
    if config.ENABLE_AUTH and path.startswith("/api/") and not path.startswith("/api/auth") and path != "/api/config":
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
mediux = MediuxClient()
renderer = TitleCardRenderer()

@app.on_event("startup")
def on_startup():
    start_scheduler()
    plex_listener.start()
    logger.info("PlexPosters API and Live AlertListener started.")

@app.on_event("shutdown")
def on_shutdown():
    plex_listener.stop()
    logger.info("PlexPosters API and Live AlertListener stopped.")

# ----------------------------------------------------
# API ENDPOINTS
# ----------------------------------------------------

@app.get("/api/config")
def get_config_info():
    """Return app settings including TEST_MODE, listener status, and auth flag."""
    from backend.config import TEST_MODE, PLEX_TV_LIBRARY, POLL_INTERVAL_HOURS
    return {
        "test_mode": TEST_MODE,
        "tv_library": PLEX_TV_LIBRARY,
        "poll_interval_hours": POLL_INTERVAL_HOURS,
        "listener_connected": plex_listener.is_connected,
        "auth_enabled": config.ENABLE_AUTH
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
    return {"shows": shows}

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

    # Fetch TMDb show info (genres, overview)
    tmdb_info = None
    if tmdb_id:
        tmdb_info = tmdb.get_show_details(tmdb_id)

    # Request 2: If style doesn't exist yet, check auto_gemini setting before querying Gemini
    auto_gemini = get_setting("auto_gemini_suggestion", "true").lower() == "true"
    initial_ai_generated = False
    ai_error = None
    if auto_gemini and not show.get("has_custom_style") and tmdb_info and ai_styler.api_key:
        try:
            logger.info(f"✨ Generating initial AI style suggestion for '{show['title']}'...")
            ai_style = ai_styler.suggest_style(
                show_title=show["title"],
                genres=tmdb_info.get("genres", []),
                overview=tmdb_info.get("overview", "")
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
        "ai_error": ai_error
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

    update_show_tmdb_id(rating_key, tmdb_id, poster_url=poster_url, backdrop_url=backdrop_url)
    updated_show = get_show(rating_key)
    return {"status": "success", "show": updated_show, "tmdb_info": details}

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
        raise HTTPException(status_code=404, detail="Show not found")

    tmdb_id = show.get("tmdb_id")
    season_num = payload.get("season_number", 1)
    episode_num = payload.get("episode_number", 1)
    episode_title = payload.get("episode_title", "Sample Episode Title")

    style = {**show, **payload}

    # Request 5: Compute hash and check preview cache for instantaneous load
    cache_key = hashlib.md5(json.dumps({
        "rk": rating_key,
        "s": season_num,
        "e": episode_num,
        "t": episode_title,
        "pos": style.get("text_position"),
        "font": style.get("font_family"),
        "c": style.get("font_color"),
        "sc": style.get("subheading_color"),
        "icon": style.get("subheading_icon"),
        "gw": style.get("gradient_width_pct"),
        "go": style.get("gradient_opacity_pct"),
        "sub": style.get("show_subheading")
    }, sort_keys=True).encode()).hexdigest()

    cached_preview = PREVIEWS_DIR / f"{cache_key}.jpg"
    if cached_preview.exists():
        return FileResponse(cached_preview, media_type="image/jpeg")

    # Fetch still
    still_path = tmdb.get_episode_still(tmdb_id, season_num, episode_num)
    if not still_path:
        raise HTTPException(status_code=404, detail="Could not fetch episode still from TMDb")

    card_img = renderer.render(
        base_image_path=still_path,
        episode_title=episode_title,
        season_num=season_num,
        episode_num=episode_num,
        style_config=style
    )

    card_img.save(cached_preview, format="JPEG", quality=92)
    return FileResponse(cached_preview, media_type="image/jpeg")

@app.post("/api/shows/{rating_key}/apply")
def apply_cards_to_show(rating_key: str, payload: dict = Body(default={})):
    """Download or generate cards and upload them to Plex for this show."""
    force_all = payload.get("force_all", True)
    force_live = payload.get("force_live", False)
    res = sync_mgr.sync_show(rating_key, force_all=force_all, force_live=force_live)
    return res

@app.post("/api/shows/{rating_key}/apply-stream")
def apply_cards_to_show_stream(rating_key: str, payload: dict = Body(default={})):
    """Stream card application progress as Newline-Delimited JSON (NDJSON)."""
    import json
    force_all = payload.get("force_all", True)
    force_live = payload.get("force_live", False)

    def event_stream():
        for event in sync_mgr.sync_show_generator(rating_key, force_all=force_all, force_live=force_live):
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

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
    user_prompt = payload.get("prompt", "")

    suggestion = ai_styler.suggest_style(
        show_title=show["title"],
        genres=genres,
        overview=overview,
        user_prompt=user_prompt
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
