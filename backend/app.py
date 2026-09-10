import logging
import base64
import io
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.config import BASE_DIR, HOST, PORT, CUSTOM_FONTS_DIR
from backend.db import init_db, get_all_shows, get_show, update_show_mode, update_show_style
from backend.sync_manager import SyncManager
from backend.ai_styler import AIStyler
from backend.tmdb_client import TMDbClient
from backend.mediux_client import MediuxClient
from backend.generator.renderer import TitleCardRenderer
from backend.scheduler import start_scheduler

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
    logger.info("PlexPosters API started.")

# ----------------------------------------------------
# API ENDPOINTS
# ----------------------------------------------------

@app.get("/api/config")
def get_config_info():
    """Return app settings including TEST_MODE status."""
    from backend.config import TEST_MODE, PLEX_TV_LIBRARY, POLL_INTERVAL_HOURS
    return {
        "test_mode": TEST_MODE,
        "tv_library": PLEX_TV_LIBRARY,
        "poll_interval_hours": POLL_INTERVAL_HOURS
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
    available_sets = []
    if tmdb_id:
        try:
            available_sets = mediux.get_show_sets(tmdb_id)
        except Exception as e:
            logger.warning(f"Could not load MediUX sets: {e}")

    # Fetch TMDb show info (genres, overview)
    tmdb_info = None
    if tmdb_id:
        tmdb_info = tmdb.get_show_details(tmdb_id)

    # Request 2 & 4: If style doesn't exist yet, request Gemini suggested default on first view and cache it
    if not show.get("has_custom_style") and tmdb_info and ai_styler.api_key:
        try:
            logger.info(f"✨ Generating initial AI style suggestion for '{show['title']}'...")
            ai_style = ai_styler.suggest_style(
                show_title=show["title"],
                genres=tmdb_info.get("genres", []),
                overview=tmdb_info.get("overview", "")
            )
            update_show_style(rating_key, {**ai_style, "has_custom_style": 1})
            show = get_show(rating_key)
        except Exception as e:
            logger.warning(f"Could not auto-generate AI style for show {show['title']}: {e}")

    return {
        "show": show,
        "episodes": episodes,
        "available_sets": available_sets,
        "tmdb_info": tmdb_info
    }

@app.post("/api/shows/{rating_key}/mode")
def set_show_mode(rating_key: str, payload: dict = Body(...)):
    """Update show mode ('auto', 'generator_only', 'mediux_locked', 'ignored') and set URL."""
    mode = payload.get("mode", "auto")
    mediux_set_url = payload.get("mediux_set_url")
    update_show_mode(rating_key, mode, mediux_set_url)
    return {"status": "success", "mode": mode, "mediux_set_url": mediux_set_url}

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
def apply_cards_to_show(rating_key: str):
    """Download or generate cards and upload them to Plex for this show."""
    res = sync_mgr.sync_show(rating_key)
    return res

@app.post("/api/shows/{rating_key}/ai-style")
def ai_suggest_style(rating_key: str, payload: dict = Body(...)):
    """Use Gemini AI to analyze the show and suggest typography & colors."""
    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    tmdb_id = show.get("tmdb_id")
    tmdb_info = tmdb.get_show_details(tmdb_id) if tmdb_id else {}
    
    genres = tmdb_info.get("genres", [])
    overview = tmdb_info.get("overview", "")
    user_prompt = payload.get("prompt", "")

    suggestion = ai_styler.suggest_style(
        show_title=show["title"],
        genres=genres,
        overview=overview,
        user_prompt=user_prompt
    )
    return suggestion

# Mount built React frontend if dist exists, otherwise fallback to frontend dir
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    frontend_dir = BASE_DIR / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
