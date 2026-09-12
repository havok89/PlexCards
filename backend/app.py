import logging
import base64
import hashlib
import io
import re
import time
import requests
from PIL import Image
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from backend import config
from backend.config import BASE_DIR, HOST, PORT, CUSTOM_FONTS_DIR, POSTERS_DIR, FONTS_DIR, STILLS_DIR, PREVIEWS_DIR
from backend.db import (
    init_db, get_all_shows, get_show, update_show_mode, update_show_style,
    get_setting, set_setting, get_all_settings, bulk_update_show_modes,
    update_show_tmdb_id, get_all_indexed_libraries,
    upsert_movie, get_all_movies as db_get_all_movies, get_movie,
    record_movie_poster, revert_movie_poster_record,
    upsert_collection, get_all_collections, get_collection, record_collection_poster
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

from backend.version import __version__

app = FastAPI(title="PlexCards", version=__version__)

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
    if config.ENABLE_AUTH and path.startswith("/api/") and not path.startswith("/api/auth") and path != "/api/config" and "/poster" not in path and not path.startswith("/api/fonts/file"):
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
        "version": __version__,
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

@app.get("/api/fonts/file/{filename}")
def get_font_file(filename: str):
    """Serve font file (.ttf / .otf) for live client-side typography previews in the UI."""
    from fastapi.responses import FileResponse
    safe_name = Path(filename).name
    custom_path = CUSTOM_FONTS_DIR / safe_name
    if custom_path.exists() and custom_path.is_file():
        media_type = "font/otf" if safe_name.endswith(".otf") else "font/ttf"
        return FileResponse(custom_path, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000"})

    font_path = FONTS_DIR / safe_name
    if font_path.exists() and font_path.is_file():
        media_type = "font/otf" if safe_name.endswith(".otf") else "font/ttf"
        return FileResponse(font_path, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000"})

    raise HTTPException(status_code=404, detail="Font file not found")

@app.get("/api/plex/libraries")
def get_plex_libraries():
    """List all TV and Movie libraries available from Plex Media Server with fallback to indexed libraries."""
    libraries = []
    try:
        libraries = sync_mgr.plex.get_all_sections()
    except Exception as e:
        logger.warning(f"Could not fetch sections live from Plex: {e}")
        indexed = get_all_indexed_libraries()
        for idx in indexed:
            libraries.append({
                "key": str(idx["library_section_id"]),
                "title": idx["library_name"],
                "type": "show"
            })

    active_tv_lib = get_setting("active_plex_library", None)
    if not active_tv_lib:
        tv_libs = [l for l in libraries if l.get("type") == "show"]
        if tv_libs:
            matching = [lib for lib in tv_libs if lib["title"].lower() == config.PLEX_TV_LIBRARY.lower()]
            active_tv_lib = matching[0]["key"] if matching else tv_libs[0]["key"]
            set_setting("active_plex_library", str(active_tv_lib))

    active_movie_lib = get_setting("active_plex_movie_library", None)
    if not active_movie_lib:
        movie_libs = [l for l in libraries if l.get("type") == "movie"]
        if movie_libs:
            matching = [lib for lib in movie_libs if lib["title"].lower() == config.PLEX_MOVIE_LIBRARY.lower()]
            active_movie_lib = matching[0]["key"] if matching else movie_libs[0]["key"]
            set_setting("active_plex_movie_library", str(active_movie_lib))

    return {
        "libraries": libraries,
        "active_library": active_tv_lib,
        "active_tv_library": active_tv_lib,
        "active_movie_library": active_movie_lib
    }

@app.post("/api/plex/libraries/switch")
def switch_plex_library(payload: dict = Body(...)):
    """Switch active Plex TV or Movie library."""
    library_key = str(payload.get("library_key", "")).strip()
    library_type = payload.get("library_type")
    if not library_key:
        raise HTTPException(status_code=400, detail="library_key is required")

    if library_type == "movie":
        set_setting("active_plex_movie_library", library_key)
        logger.info(f"Switched active Plex Movie library to: {library_key}")
    else:
        set_setting("active_plex_library", library_key)
        logger.info(f"Switched active Plex TV library to: {library_key}")

    return {"status": "success", "active_library": library_key}


@app.get("/api/shows")
def list_shows(library: Optional[str] = None):
    """List all indexed TV shows with status and card statistics."""
    active_filter = None
    if library and str(library).lower() != "all":
        active_filter = str(library)

    shows = get_all_shows(library_filter=active_filter)
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

    r = None
    try:
        req_headers = {"X-Plex-Token": sync_mgr.plex.token} if any(h in target_url for h in ["127.0.0.1", "localhost", ":32400"]) else {}
        r = requests.get(target_url, headers=req_headers, timeout=(4, 10))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
        logger.warning(f"Plex read timed out for show poster {rating_key}: {net_err}. Trying TMDb fallback...")
        if show and show.get("tmdb_id"):
            try:
                details = tmdb.get_show_details(show["tmdb_id"])
                if details and details.get("poster_url"):
                    r = requests.get(details["poster_url"], timeout=(3, 8))
            except Exception as fb_err:
                logger.warning(f"TMDb fallback failed for show {rating_key}: {fb_err}")
        if not r:
            raise HTTPException(status_code=504, detail="Upstream media server timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting poster for show {rating_key}: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to poster source")

    try:
        if r and r.status_code == 200:
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
            status = r.status_code if r else 404
            logger.warning(f"Failed to fetch poster from {target_url}: HTTP {status}")
            raise HTTPException(status_code=status, detail="Could not fetch poster from origin")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing poster for show {rating_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch poster")

@app.post("/api/library/scan")
def scan_library(library: Optional[str] = None, type: Optional[str] = None):
    """Scan Plex server and index all shows or movies for the specified or active library."""
    if type == "movie":
        target = library if library is not None else get_setting("active_plex_movie_library", None)
        res = sync_mgr.scan_movie_library(target_library=target)
        return {"status": "success", "type": "movie", **res}

    target = library if library is not None else get_setting("active_plex_library", None)
    count = sync_mgr.scan_and_index_library(target_library=target)
    return {"status": "success", "type": "show", "indexed_shows": count}

@app.post("/api/movies/scan")
def scan_movies(library: Optional[str] = None):
    """Scan Plex Movie library."""
    target = library if library is not None else get_setting("active_plex_movie_library", None)
    res = sync_mgr.scan_movie_library(target_library=target)
    return {"status": "success", **res}

@app.get("/api/movies")
def list_movies(
    library: Optional[str] = None,
    collection: Optional[str] = None,
    sort: str = "title_asc",
    search: Optional[str] = None
):
    """List all indexed movies with optional filtering and sorting."""
    active_filter = None
    if library and str(library).lower() != "all":
        active_filter = str(library)

    movies = db_get_all_movies(library_filter=active_filter, collection_filter=collection, sort_by=sort)
    if search:
        s_low = search.strip().lower()
        movies = [m for m in movies if s_low in m.get("title", "").lower()]

    for m in movies:
        if m.get("poster_url"):
            up = m.get("updated_at") or ""
            ts = int(hashlib.md5(f"{m['rating_key']}_{up}_{m['poster_url']}".encode()).hexdigest()[:8], 16)
            m["poster_url"] = f"/api/movies/{m['rating_key']}/poster.jpg?v={ts}"

    return {"movies": movies}

@app.get("/api/movies/{rating_key}")
def get_movie_detail(rating_key: str):
    """Get single movie record and extra TMDb details if available."""
    movie = get_movie(rating_key)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    if movie.get("poster_url"):
        up = movie.get("updated_at") or ""
        ts = int(hashlib.md5(f"{rating_key}_{up}_{movie['poster_url']}".encode()).hexdigest()[:8], 16)
        movie["poster_url"] = f"/api/movies/{rating_key}/poster.jpg?v={ts}"

    tmdb_details = None
    if movie.get("tmdb_id"):
        tmdb_details = sync_mgr.tmdb.get_movie_details(movie["tmdb_id"])

    return {
        "movie": movie,
        "tmdb_details": tmdb_details
    }

@app.get("/api/movies/{rating_key}/poster")
@app.get("/api/movies/{rating_key}/poster.jpg")
def get_movie_poster(rating_key: str, request: Request):
    """Serve optimized, compressed movie poster with local disk caching."""
    poster_path = POSTERS_DIR / f"movie_{rating_key}.jpg"
    mtime = int(poster_path.stat().st_mtime) if poster_path.exists() else 0
    etag = f'"movie_{rating_key}_{mtime}"'
    headers = {
        "Cache-Control": "public, max-age=300, stale-while-revalidate=60",
        "ETag": etag
    }

    if poster_path.exists():
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return FileResponse(poster_path, media_type="image/jpeg", headers=headers)

    movie = get_movie(rating_key)
    target_url = movie.get("poster_url") if movie else None

    # Fallback to live Plex item if not in DB
    if not target_url and sync_mgr.plex:
        try:
            item = sync_mgr.plex.server.fetchItem(int(rating_key))
            target_url = item.posterUrl if hasattr(item, "posterUrl") else (item.thumbUrl if hasattr(item, "thumbUrl") else None)
        except Exception:
            pass

    # Fallback to TMDb
    if not target_url and movie and movie.get("tmdb_id"):
        try:
            details = sync_mgr.tmdb.get_movie_details(movie["tmdb_id"])
            if details:
                target_url = details.get("poster_url")
        except Exception:
            pass

    if not target_url:
        raise HTTPException(status_code=404, detail="Movie poster not found")

    r = None
    try:
        req_headers = {"X-Plex-Token": sync_mgr.plex.token} if any(h in target_url for h in ["127.0.0.1", "localhost", ":32400"]) else {}
        r = requests.get(target_url, headers=req_headers, timeout=(4, 10))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
        logger.warning(f"Plex read timed out for movie poster {rating_key}: {net_err}. Trying TMDb fallback...")
        if movie and movie.get("tmdb_id"):
            try:
                details = sync_mgr.tmdb.get_movie_details(movie["tmdb_id"])
                if details and details.get("poster_url"):
                    r = requests.get(details["poster_url"], timeout=(3, 8))
            except Exception as fb_err:
                logger.warning(f"TMDb fallback failed for {rating_key}: {fb_err}")
        if not r:
            raise HTTPException(status_code=504, detail="Upstream media server timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting movie poster for {rating_key}: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to poster source")

    try:
        if r and r.status_code == 200:
            try:
                from PIL import Image
                with Image.open(io.BytesIO(r.content)) as im:
                    if im.width > 420:
                        new_h = int(im.height * (420.0 / im.width))
                        im = im.resize((420, new_h), Image.Resampling.LANCZOS)
                    im.convert("RGB").save(poster_path, format="JPEG", quality=82, optimize=True)
            except Exception as resize_err:
                logger.warning(f"Could not resize movie poster: {resize_err}")
                with open(poster_path, "wb") as f:
                    f.write(r.content)

            return FileResponse(poster_path, media_type="image/jpeg", headers=headers)
        else:
            status = r.status_code if r else 404
            raise HTTPException(status_code=status, detail="Could not fetch movie poster from origin")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing movie poster for {rating_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process movie poster")

@app.get("/api/movies/{rating_key}/posters")
def get_movie_poster_options(rating_key: str):
    """Fetch poster options from MediUX and TMDb for a movie."""
    movie = get_movie(rating_key)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    tmdb_id = movie.get("tmdb_id")
    movie_title = movie.get("title", "")
    movie_year = movie.get("year")
    mediux_sets = []
    tmdb_posters = []

    if tmdb_id:
        try:
            raw_sets = sync_mgr.mediux.get_movie_sets(tmdb_id)
            # Filter out franchise/collection sets so Movie View only shows artwork for THIS movie
            collection_kws = ["collection", "boxset", "box set", "anthology", "trilogy", "quadrilogy", "saga", "duology", "franchise", "series"]
            clean_movie = re.sub(r'[^a-z0-9]', '', movie_title.lower())

            for s in raw_sets:
                s_name_l = s.get("set_name", "").lower()
                # Skip collection sets
                if any(kw in s_name_l for kw in collection_kws):
                    continue

                filtered_posters = []
                for p in s.get("posters", []):
                    p_title = p.get("title", "")
                    p_title_l = p_title.lower()
                    if any(kw in p_title_l for kw in collection_kws):
                        continue

                    clean_p = re.sub(r'[^a-z0-9]', '', p_title.lower())
                    if clean_movie in clean_p or clean_p in clean_movie:
                        y_match = re.search(r'\b(19\d\d|20\d\d)\b', p_title)
                        if y_match and movie_year:
                            p_year = int(y_match.group(1))
                            if abs(p_year - movie_year) > 1:
                                continue

                        is_sequel_poster = bool(re.search(r'\b(ii|iii|iv|v|vi|2|3|4|5|6|7|8|part\s*2|part\s*ii)\b', p_title_l))
                        is_sequel_movie = bool(re.search(r'\b(ii|iii|iv|v|vi|2|3|4|5|6|7|8|part\s*2|part\s*ii)\b', movie_title.lower()))
                        if is_sequel_poster and not is_sequel_movie:
                            continue

                        filtered_posters.append(p)
                    elif not clean_movie:
                        filtered_posters.append(p)

                if filtered_posters:
                    s_copy = dict(s)
                    s_copy["posters"] = filtered_posters
                    s_copy["poster_url"] = filtered_posters[0]["url"]
                    mediux_sets.append(s_copy)
        except Exception as e:
            logger.warning(f"Failed to fetch MediUX sets for movie {tmdb_id}: {e}")

        try:
            tmdb_posters = sync_mgr.tmdb.get_movie_posters(tmdb_id)
        except Exception as e:
            logger.warning(f"Failed to fetch TMDb posters for movie {tmdb_id}: {e}")

    up = movie.get("updated_at") or ""
    ts = int(hashlib.md5(f"{rating_key}_{up}_{movie.get('poster_url', '')}".encode()).hexdigest()[:8], 16)
    return {
        "rating_key": rating_key,
        "title": movie.get("title"),
        "year": movie.get("year"),
        "tmdb_id": tmdb_id,
        "current_poster": f"/api/movies/{rating_key}/poster.jpg?v={ts}" if movie.get("poster_url") else None,
        "mediux_sets": mediux_sets,
        "tmdb_posters": tmdb_posters
    }

@app.post("/api/movies/{rating_key}/upload-poster")
async def upload_movie_poster_endpoint(
    rating_key: str,
    file: UploadFile = File(...)
):
    """Upload a custom poster image for a movie."""
    movie = get_movie(rating_key)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    try:
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    dest_path = POSTERS_DIR / f"upload_movie_{rating_key}.jpg"
    img.save(dest_path, "JPEG", quality=95)

    t_nonce = int(time.time())
    return {
        "status": "success",
        "poster_url": f"/api/movies/{rating_key}/uploaded-poster?t={t_nonce}",
        "file_path": str(dest_path)
    }

@app.get("/api/movies/{rating_key}/uploaded-poster")
def get_uploaded_movie_poster(rating_key: str):
    """Serve the recently uploaded custom poster for a movie."""
    dest_path = POSTERS_DIR / f"upload_movie_{rating_key}.jpg"
    if not dest_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded poster not found")
    return FileResponse(dest_path, media_type="image/jpeg")

@app.post("/api/movies/{rating_key}/apply-poster")
def apply_movie_poster(rating_key: str, payload: dict = Body(...)):
    """Apply a chosen poster URL or uploaded file to the movie in Plex (or simulate if TEST_MODE)."""
    poster_url = payload.get("poster_url")
    file_path = payload.get("file_path")
    source = payload.get("source", "mediux")
    force_live = payload.get("force_live", False)
    if not poster_url and not file_path:
        raise HTTPException(status_code=400, detail="poster_url or file_path is required")

    from backend.config import TEST_MODE, TEST_OUTPUT_DIR
    is_test = TEST_MODE and not force_live

    movie = get_movie(rating_key)
    title = movie.get("title", f"movie_{rating_key}") if movie else f"movie_{rating_key}"

    try:
        # Check if local uploaded file is present
        local_file = None
        if file_path and Path(file_path).exists():
            local_file = Path(file_path)
        elif poster_url and (POSTERS_DIR / f"upload_movie_{rating_key}.jpg").exists() and "/uploaded-poster" in poster_url:
            local_file = POSTERS_DIR / f"upload_movie_{rating_key}.jpg"

        if is_test:
            clean_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', title).strip()
            test_dir = TEST_OUTPUT_DIR / "Movies" / clean_title
            test_dir.mkdir(parents=True, exist_ok=True)
            test_path = test_dir / f"poster_{source}.jpg"

            if local_file:
                import shutil
                shutil.copyfile(local_file, test_path)
            else:
                req_headers = {"X-Plex-Token": sync_mgr.plex.token} if any(h in poster_url for h in ["127.0.0.1", "localhost", ":32400"]) else {}
                r = requests.get(poster_url, headers=req_headers, timeout=10)
                if r.status_code == 200:
                    with open(test_path, "wb") as f:
                        f.write(r.content)
            logger.info(f"🧪 [TEST MODE] Saved movie poster to {test_path} without uploading to Plex.")
            return {
                "status": "success",
                "test_mode": True,
                "message": f"🧪 Test Mode: Saved poster locally to cache/test_output/ without modifying Plex.",
                "poster_url": poster_url or f"/api/movies/{rating_key}/uploaded-poster"
            }
        else:
            if local_file:
                sync_mgr.plex.upload_movie_poster(rating_key, str(local_file), force_live=force_live)
                record_movie_poster(rating_key, f"/api/movies/{rating_key}/poster.jpg?v={int(time.time())}", source=source)
                import shutil
                shutil.copyfile(local_file, POSTERS_DIR / f"movie_{rating_key}.jpg")
            else:
                sync_mgr.plex.upload_movie_poster(rating_key, poster_url, force_live=force_live)
                record_movie_poster(rating_key, poster_url, source=source)
                # Invalidate local cached poster
                cached_file = POSTERS_DIR / f"movie_{rating_key}.jpg"
                if cached_file.exists():
                    try:
                        cached_file.unlink()
                    except Exception:
                        pass

            return {
                "status": "success",
                "test_mode": False,
                "message": "Poster successfully applied to movie in Plex",
                "poster_url": f"/api/movies/{rating_key}/poster.jpg?t={int(time.time())}"
            }
    except Exception as e:
        logger.error(f"Failed to apply poster to movie {rating_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/movies/{rating_key}/revert-poster")
def revert_movie_poster_endpoint(rating_key: str, payload: dict = Body(default={})):
    """Revert a movie poster back to Plex default."""
    force_live = payload.get("force_live", False)
    from backend.config import TEST_MODE
    is_test = TEST_MODE and not force_live

    try:
        if is_test:
            logger.info(f"🧪 [TEST MODE] Skipped reverting movie ID {rating_key} in Plex.")
            return {
                "status": "success",
                "test_mode": True,
                "message": "🧪 Test Mode: Revert simulated without modifying Plex."
            }
        else:
            sync_mgr.plex.revert_movie_poster(rating_key, force_live=force_live)
            revert_movie_poster_record(rating_key)

            cached_file = POSTERS_DIR / f"movie_{rating_key}.jpg"
            if cached_file.exists():
                try:
                    cached_file.unlink()
                except Exception:
                    pass

            return {
                "status": "success",
                "test_mode": False,
                "message": "Poster reverted to default in Plex"
            }
    except Exception as e:
        logger.error(f"Failed to revert movie poster {rating_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/collections")
def list_collections(library: Optional[str] = None):
    """List all movie collections with child movie counts."""
    active_filter = None
    if library and str(library).lower() != "all":
        active_filter = str(library)

    colls = get_all_collections(library_filter=active_filter)
    for c in colls:
        if c.get("poster_url"):
            up = c.get("updated_at") or ""
            ts = int(hashlib.md5(f"{c['rating_key']}_{up}_{c['poster_url']}".encode()).hexdigest()[:8], 16)
            c["poster_url"] = f"/api/collections/{c['rating_key']}/poster.jpg?v={ts}"

    return {"collections": colls}

@app.get("/api/collections/{rating_key}")
def get_collection_detail(rating_key: str):
    """Get collection details along with member movies."""
    coll = get_collection(rating_key)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    up = coll.get("updated_at") or ""
    ts = int(hashlib.md5(f"{rating_key}_{up}_{coll.get('poster_url', '')}".encode()).hexdigest()[:8], 16)
    if coll.get("poster_url"):
        coll["poster_url"] = f"/api/collections/{rating_key}/poster.jpg?v={ts}"

    movies = db_get_all_movies(collection_filter=coll["title"])
    for m in movies:
        if m.get("poster_url"):
            m_up = m.get("updated_at") or ""
            m_ts = int(hashlib.md5(f"{m['rating_key']}_{m_up}_{m['poster_url']}".encode()).hexdigest()[:8], 16)
            m["poster_url"] = f"/api/movies/{m['rating_key']}/poster.jpg?v={m_ts}"

    return {
        "collection": coll,
        "movies": movies
    }

@app.get("/api/collections/{rating_key}/poster")
@app.get("/api/collections/{rating_key}/poster.jpg")
def get_collection_poster_endpoint(rating_key: str, request: Request):
    """Serve cached collection poster."""
    poster_path = POSTERS_DIR / f"coll_{rating_key}.jpg"
    mtime = int(poster_path.stat().st_mtime) if poster_path.exists() else 0
    etag = f'"coll_{rating_key}_{mtime}"'
    headers = {
        "Cache-Control": "public, max-age=300, stale-while-revalidate=60",
        "ETag": etag
    }

    if poster_path.exists():
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return FileResponse(poster_path, media_type="image/jpeg", headers=headers)

    coll = get_collection(rating_key)
    target_url = coll.get("poster_url") if coll else None

    if not target_url and sync_mgr.plex:
        try:
            item = sync_mgr.plex.server.fetchItem(int(rating_key))
            target_url = item.posterUrl if hasattr(item, "posterUrl") else (item.thumbUrl if hasattr(item, "thumbUrl") else None)
        except Exception:
            pass

    if not target_url:
        raise HTTPException(status_code=404, detail="Collection poster not found")

    r = None
    try:
        from PIL import Image
        req_headers = {"X-Plex-Token": sync_mgr.plex.token} if any(h in target_url for h in ["127.0.0.1", "localhost", ":32400"]) else {}
        r = requests.get(target_url, headers=req_headers, timeout=(4, 10))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as net_err:
        logger.warning(f"Plex read timed out for collection poster {rating_key}: {net_err}")
        raise HTTPException(status_code=504, detail="Upstream media server timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting collection poster for {rating_key}: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to collection poster source")

    try:
        if r and r.status_code == 200:
            try:
                with Image.open(io.BytesIO(r.content)) as im:
                    if im.width > 420:
                        new_h = int(im.height * (420.0 / im.width))
                        im = im.resize((420, new_h), Image.Resampling.LANCZOS)
                    im.convert("RGB").save(poster_path, format="JPEG", quality=82, optimize=True)
            except Exception as resize_err:
                logger.warning(f"Could not resize collection poster: {resize_err}")
                with open(poster_path, "wb") as f:
                    f.write(r.content)

            return FileResponse(poster_path, media_type="image/jpeg", headers=headers)
        else:
            status = r.status_code if r else 404
            raise HTTPException(status_code=status, detail="Could not fetch collection poster")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing collection poster for {rating_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch collection poster")

@app.get("/api/collections/{rating_key}/posters")
def get_collection_posters_endpoint(rating_key: str):
    """Fetch franchise sets from MediUX and TMDb for a collection."""
    coll = get_collection(rating_key)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    movies = db_get_all_movies(collection_filter=coll["title"])
    for m in movies:
        if m.get("poster_url"):
            m["poster_url"] = f"/api/movies/{m['rating_key']}/poster.jpg"

    tmdb_coll_id = coll.get("tmdb_collection_id")

    # 1. Auto-resolve tmdb_collection_id if not present
    if not tmdb_coll_id:
        movie_tmdb_ids = [m["tmdb_id"] for m in movies if m.get("tmdb_id")]
        for m_id in movie_tmdb_ids:
            try:
                m_details = sync_mgr.tmdb.get_movie_details(m_id)
                if m_details and m_details.get("collection") and m_details["collection"].get("id"):
                    tmdb_coll_id = m_details["collection"]["id"]
                    break
            except Exception as e:
                logger.debug(f"Could not get collection info from movie {m_id}: {e}")

        if not tmdb_coll_id:
            try:
                search_res = sync_mgr.tmdb.search_collection(coll["title"])
                if search_res:
                    tmdb_coll_id = search_res[0]["id"]
            except Exception as e:
                logger.debug(f"Could not search TMDb collection for {coll['title']}: {e}")

        if tmdb_coll_id:
            coll["tmdb_collection_id"] = tmdb_coll_id
            upsert_collection(coll)

    mediux_sets = []
    tmdb_posters = []

    # 2. Fetch TMDb collection posters & MediUX boxsets if ID resolved
    if tmdb_coll_id:
        try:
            tmdb_posters = sync_mgr.tmdb.get_collection_posters(tmdb_coll_id)
        except Exception as e:
            logger.warning(f"Failed to fetch TMDb posters for collection {tmdb_coll_id}: {e}")

        try:
            mediux_sets = sync_mgr.mediux.get_collection_sets(tmdb_coll_id)
        except Exception as e:
            logger.warning(f"Failed to fetch MediUX sets for collection {tmdb_coll_id}: {e}")

    # 3. Enhanced MediUX discovery: Check franchise sets on member movies
    # MediUX creators frequently attach franchise sets directly to the movies in the series.
    if not mediux_sets:
        seen_set_ids = set()
        movie_tmdb_ids = [m["tmdb_id"] for m in movies if m.get("tmdb_id")]
        for m_id in movie_tmdb_ids:
            try:
                m_sets = sync_mgr.mediux.get_movie_sets(m_id)
                for ms in m_sets:
                    if ms["id"] in seen_set_ids:
                        continue
                    seen_set_ids.add(ms["id"])

                    # If this set has multiple posters or mentions collection/series, treat as franchise set
                    set_posters = ms.get("posters", [])
                    if len(set_posters) > 1 or any(w in ms.get("set_name", "").lower() for w in ["collection", "series", "trilogy", "quadrilogy", "saga", "boxset"]):
                        boxset_url = None
                        movie_posters = []
                        for p in set_posters:
                            if any(w in p["title"].lower() for w in ["collection", "boxset", "series", "trilogy", "quadrilogy", "saga"]):
                                if not boxset_url:
                                    boxset_url = p["url"]
                            else:
                                movie_posters.append(p)

                        if not boxset_url and ms.get("poster_url"):
                            boxset_url = ms["poster_url"]

                        mediux_sets.append({
                            "id": ms["id"],
                            "set_name": ms["set_name"],
                            "creator": ms["creator"],
                            "date_updated": ms["date_updated"],
                            "set_url": ms["set_url"],
                            "collection_poster_url": boxset_url,
                            "movie_posters": movie_posters or set_posters
                        })
            except Exception as e:
                logger.debug(f"Error checking MediUX movie sets for movie {m_id}: {e}")

    return {
        "rating_key": rating_key,
        "title": coll.get("title"),
        "tmdb_collection_id": tmdb_coll_id,
        "applied_mediux_set_id": coll.get("applied_mediux_set_id"),
        "movies": movies,
        "mediux_sets": mediux_sets,
        "tmdb_posters": tmdb_posters
    }

@app.post("/api/collections/{rating_key}/apply-set")
def apply_collection_set(rating_key: str, payload: dict = Body(...)):
    """Batch apply franchise collection artwork: collection poster and/or child movie posters."""
    coll_poster_url = payload.get("collection_poster_url")
    movie_posters = payload.get("movie_posters", [])
    mediux_set_id = payload.get("mediux_set_id")
    force_live = payload.get("force_live", False)

    from backend.config import TEST_MODE, TEST_OUTPUT_DIR
    is_test = TEST_MODE and not force_live

    coll = get_collection(rating_key)
    coll_title = coll.get("title", f"collection_{rating_key}") if coll else f"collection_{rating_key}"

    applied_count = 0
    errors = []

    if is_test:
        clean_title = re.sub(r'[^a-zA-Z0-9_\- ]', '', coll_title).strip()
        test_dir = TEST_OUTPUT_DIR / "Collections" / clean_title
        test_dir.mkdir(parents=True, exist_ok=True)

        if coll_poster_url:
            try:
                req_headers = {"X-Plex-Token": sync_mgr.plex.token} if any(h in coll_poster_url for h in ["127.0.0.1", "localhost", ":32400"]) else {}
                r = requests.get(coll_poster_url, headers=req_headers, timeout=10)
                if r.status_code == 200:
                    with open(test_dir / "boxset_cover.jpg", "wb") as f:
                        f.write(r.content)
                applied_count += 1
            except Exception as e:
                errors.append(f"Failed to test-save collection boxset: {e}")

        for idx, mp in enumerate(movie_posters):
            m_url = mp.get("poster_url")
            m_rk = mp.get("movie_rating_key")
            if m_url:
                try:
                    r = requests.get(m_url, timeout=10)
                    if r.status_code == 200:
                        with open(test_dir / f"movie_{m_rk or idx}.jpg", "wb") as f:
                            f.write(r.content)
                    applied_count += 1
                except Exception:
                    pass

        logger.info(f"🧪 [TEST MODE] Saved {applied_count} franchise collection posters to {test_dir} without modifying Plex.")
        return {
            "status": "success",
            "test_mode": True,
            "applied_count": applied_count,
            "errors": errors,
            "message": f"🧪 Test Mode: Saved {applied_count} franchise posters locally to cache/test_output/ without modifying Plex."
        }

    # Live Mode: upload to Plex and update local database
    # 1. Apply collection boxset poster
    if coll_poster_url:
        try:
            sync_mgr.plex.upload_collection_poster(rating_key, coll_poster_url, force_live=force_live)
            record_collection_poster(rating_key, coll_poster_url, mediux_set_id=mediux_set_id)
            applied_count += 1

            cached_file = POSTERS_DIR / f"coll_{rating_key}.jpg"
            if cached_file.exists():
                try:
                    cached_file.unlink()
                except Exception:
                    pass

            # Pre-cache the new image right away so browser gets it immediately
            try:
                req_headers = {"X-Plex-Token": sync_mgr.plex.token} if any(h in coll_poster_url for h in ["127.0.0.1", "localhost", ":32400"]) else {}
                r = requests.get(coll_poster_url, headers=req_headers, timeout=10)
                if r.status_code == 200:
                    from PIL import Image
                    with Image.open(io.BytesIO(r.content)) as im:
                        if im.width > 420:
                            new_h = int(im.height * (420.0 / im.width))
                            im = im.resize((420, new_h), Image.Resampling.LANCZOS)
                        im.convert("RGB").save(cached_file, format="JPEG", quality=82, optimize=True)
            except Exception as cache_err:
                logger.debug(f"Could not pre-cache collection poster: {cache_err}")
        except Exception as e:
            errors.append(f"Failed to apply collection poster: {e}")

    # 2. Apply each child movie poster
    for mp in movie_posters:
        m_rk = mp.get("movie_rating_key")
        m_url = mp.get("poster_url")
        if m_rk and m_url:
            try:
                sync_mgr.plex.upload_movie_poster(m_rk, m_url, force_live=force_live)
                record_movie_poster(m_rk, m_url, source="mediux_franchise_set")
                applied_count += 1

                cached_file = POSTERS_DIR / f"movie_{m_rk}.jpg"
                if cached_file.exists():
                    try:
                        cached_file.unlink()
                    except Exception:
                        pass
            except Exception as e:
                errors.append(f"Failed to apply movie poster {m_rk}: {e}")

    return {
        "status": "success",
        "test_mode": False,
        "applied_count": applied_count,
        "errors": errors
    }

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

    episodes = []
    try:
        episodes = sync_mgr.plex.get_show_episodes(rating_key)
    except Exception as e:
        logger.warning(f"Could not fetch episodes from Plex API for show {rating_key}: {e}. Falling back to local DB.")
        from backend.db import get_episodes_for_show
        episodes = get_episodes_for_show(rating_key)
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

# --- Discord Webhook Notification Endpoints ---
@app.post("/api/notifications/discord/test")
def test_discord_webhook(payload: dict = Body(...)):
    """Dispatch a test embed to verify Discord webhook connectivity."""
    from backend.discord_notifier import discord_notifier
    target_url = payload.get("webhook_url")
    result = discord_notifier.send_test_notification(webhook_url=target_url)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result

# --- Season-Specific Style Override Endpoints ---
@app.get("/api/shows/{rating_key}/seasons/styles")
def get_show_season_styles_endpoint(rating_key: str):
    """Retrieve all season-specific style overrides for a show."""
    from backend.db import get_all_season_styles
    return {"season_styles": get_all_season_styles(rating_key)}

@app.get("/api/shows/{rating_key}/seasons/{season_number}/style")
def get_season_style_endpoint(rating_key: str, season_number: int):
    """Get season-specific style override and effective style for a season."""
    from backend.db import get_season_style, get_effective_style
    override = get_season_style(rating_key, season_number)
    effective = get_effective_style(rating_key, season_number)
    return {
        "season_number": season_number,
        "override": override,
        "effective": effective,
        "has_override": bool(override)
    }

@app.post("/api/shows/{rating_key}/seasons/{season_number}/style")
def set_season_style_endpoint(rating_key: str, season_number: int, payload: dict = Body(...)):
    """Save or update custom style override for a specific season."""
    from backend.db import set_season_style, get_effective_style
    set_season_style(rating_key, season_number, payload)
    effective = get_effective_style(rating_key, season_number)
    return {
        "status": "success",
        "season_number": season_number,
        "override": payload,
        "effective": effective
    }

@app.delete("/api/shows/{rating_key}/seasons/{season_number}/style")
def delete_season_style_endpoint(rating_key: str, season_number: int):
    """Delete season-specific style override, reverting to show default."""
    from backend.db import delete_season_style, get_effective_style
    delete_season_style(rating_key, season_number)
    effective = get_effective_style(rating_key, season_number)
    return {
        "status": "success",
        "season_number": season_number,
        "effective": effective
    }

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

    from backend.db import get_effective_style
    effective_base = get_effective_style(rating_key, season_num)
    style = {**effective_base, **payload}
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

    custom_filename = f"custom_{rating_key}_s{season_number}e{episode_number}.jpg"
    custom_file = STILLS_DIR / custom_filename
    override = get_episode_still_override(rating_key, season_number, episode_number)

    if custom_file.exists():
        custom_key = f"custom:{custom_filename}"
        stills.insert(0, {
            "file_path": custom_key,
            "thumb_url": f"/api/shows/{rating_key}/raw-still?season_number={season_number}&episode_number={episode_number}&custom=1",
            "full_url": f"/api/shows/{rating_key}/raw-still?season_number={season_number}&episode_number={episode_number}&custom=1",
            "width": 1920,
            "height": 1080,
            "aspect_ratio": 1.78,
            "is_16_9": True,
            "vote_average": 10.0,
            "vote_count": 1,
            "quality_score": 100,
            "is_top_pick": False,
            "is_selected": (override == custom_key or override == custom_filename),
            "provider": "custom"
        })

    for s in stills:
        if override:
            s["is_selected"] = (s["file_path"] == override or (s.get("provider") == "custom" and override.startswith("custom:")))
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
    if still_path.startswith("custom:") or still_path.startswith("custom_"):
        clean_name = still_path.replace("custom:", "").split("?")[0]
        cached_path = STILLS_DIR / clean_name
    elif (still_path.startswith("http://") or still_path.startswith("https://")) and show.get("tvdb_id"):
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

@app.post("/api/shows/{rating_key}/episodes/{season_number}/{episode_number}/custom-still")
async def upload_custom_still(
    rating_key: str,
    season_number: int,
    episode_number: int,
    file: UploadFile = File(...)
):
    """Upload a custom screencap / still frame for an episode."""
    from PIL import Image
    from backend.db import set_episode_still_override

    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    try:
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    # Resize to 1920x1080 if not already
    orig_w, orig_h = img.size
    if orig_w != 1920 or orig_h != 1080:
        img = img.resize((1920, 1080), Image.Resampling.LANCZOS)

    custom_filename = f"custom_{rating_key}_s{season_number}e{episode_number}.jpg"
    dest_path = STILLS_DIR / custom_filename
    img.save(dest_path, "JPEG", quality=95)

    custom_key = f"custom:{custom_filename}"
    set_episode_still_override(rating_key, season_number, episode_number, custom_key)

    # Invalidate preview cache for this rating_key
    for p in PREVIEWS_DIR.glob(f"*{rating_key}*"):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

    t_nonce = int(time.time())
    return {
        "status": "success",
        "still_path": custom_key,
        "season_number": season_number,
        "episode_number": episode_number,
        "still": {
            "file_path": custom_key,
            "thumb_url": f"/api/shows/{rating_key}/raw-still?season_number={season_number}&episode_number={episode_number}&t={t_nonce}",
            "full_url": f"/api/shows/{rating_key}/raw-still?season_number={season_number}&episode_number={episode_number}&t={t_nonce}",
            "width": 1920,
            "height": 1080,
            "aspect_ratio": 1.78,
            "is_16_9": True,
            "vote_average": 10.0,
            "vote_count": 1,
            "quality_score": 100,
            "is_top_pick": False,
            "is_selected": True,
            "provider": "custom"
        }
    }

@app.delete("/api/shows/{rating_key}/episodes/{season_number}/{episode_number}/custom-still")
def delete_custom_still(
    rating_key: str,
    season_number: int,
    episode_number: int
):
    """Delete a custom uploaded screencap / still frame for an episode and revert to default."""
    from backend.db import get_episode_still_override, delete_episode_still_override

    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    custom_filename = f"custom_{rating_key}_s{season_number}e{episode_number}.jpg"
    dest_path = STILLS_DIR / custom_filename
    if dest_path.exists():
        try:
            dest_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Could not remove custom still file {dest_path}: {e}")

    # If active override was this custom still, clear it from SQLite
    override = get_episode_still_override(rating_key, season_number, episode_number)
    if override and (override.startswith("custom:") or override.startswith("custom_") or custom_filename in override):
        delete_episode_still_override(rating_key, season_number, episode_number)

    # Invalidate preview cache for this rating_key
    for p in PREVIEWS_DIR.glob(f"*{rating_key}*"):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "status": "success",
        "message": f"Custom screencap for S{season_number:02d}E{episode_number:02d} removed."
    }

@app.get("/api/shows/{rating_key}/export-zip")
def export_show_cards_zip(
    rating_key: str,
    source: str = "auto"
):
    """Package and export all 1080p title cards for a show as a .zip archive."""
    import zipfile
    import re
    import requests

    show = get_show(rating_key)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    clean_show_title = re.sub(r'[\\/*?:"<>|]', "", show["title"]).strip()
    episodes = []
    try:
        episodes = sync_mgr.plex.get_show_episodes(rating_key)
    except Exception as e:
        logger.warning(f"Could not fetch live Plex episodes for export-zip: {e}. Falling back to DB.")
        from backend.db import get_episodes_for_show
        episodes = get_episodes_for_show(rating_key)
    if not episodes:
        raise HTTPException(status_code=404, detail="No episodes found for show")

    # Sort episodes by season and episode number
    episodes = sorted(episodes, key=lambda ep: (ep.get("season_number", 0), ep.get("episode_number", 0)))

    # Fetch MediUX set files if applicable
    mediux_cards_map = {}
    if source in ("mediux", "auto") and show.get("mediux_set_id"):
        try:
            set_data = mediux.get_set(show["mediux_set_id"])
            if set_data:
                for f in set_data.get("files", []):
                    if f.get("fileType") == "title_card" and f.get("season_number") is not None and f.get("episode_number") is not None:
                        s_key = (f["season_number"], f["episode_number"])
                        img_id = f.get("id")
                        if img_id:
                            mediux_cards_map[s_key] = f"https://images.mediux.pro/{img_id}.jpg"
        except Exception as e:
            logger.warning(f"Error fetching MediUX cards for zip export: {e}")

    zip_buffer = io.BytesIO()
    exported_count = 0
    logo_path = sync_mgr.get_show_logo_path(show)

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for ep in episodes:
            s_num = ep.get("season_number")
            e_num = ep.get("episode_number")
            ep_title = ep.get("title", f"Episode {e_num}")
            if s_num is None or e_num is None:
                continue

            clean_ep_title = re.sub(r'[\\/*?:"<>|]', "", ep_title).strip()
            # Standard Plex title card naming inside show folder
            arcname = f"{clean_show_title}/S{s_num:02d}E{e_num:02d} - {clean_ep_title}.jpg"

            # Check if MediUX card should be used
            m_url = mediux_cards_map.get((s_num, e_num))
            card_bytes = None

            if (source == "mediux" or (source == "auto" and m_url)) and m_url:
                try:
                    r = requests.get(m_url, timeout=10)
                    if r.status_code == 200:
                        card_bytes = r.content
                except Exception as e:
                    logger.warning(f"Failed to fetch MediUX card for {arcname}: {e}")

            # If no MediUX card or generator preferred, render card locally
            if not card_bytes:
                try:
                    still_file = sync_mgr.get_episode_backdrop_still(show, ep)
                    if still_file and still_file.exists():
                        card_img = sync_mgr.renderer.render(
                            base_image_path=still_file,
                            episode_title=ep_title,
                            season_num=s_num,
                            episode_num=e_num,
                            style_config=show,
                            logo_image_path=logo_path
                        )
                        img_byte_arr = io.BytesIO()
                        card_img.save(img_byte_arr, format="JPEG", quality=95)
                        card_bytes = img_byte_arr.getvalue()
                except Exception as e:
                    logger.error(f"Failed to render title card for {arcname}: {e}")

            if card_bytes:
                zip_file.writestr(arcname, card_bytes)
                exported_count += 1

    if exported_count == 0:
        raise HTTPException(status_code=500, detail="Failed to generate or retrieve any title cards for export")

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()

    filename = f"{clean_show_title}_Title_Cards.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes))
        }
    )

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

@app.post("/api/shows/{rating_key}/episodes/{season_number}/{episode_number}/revert")
def revert_card_to_native(
    rating_key: str,
    season_number: int,
    episode_number: int,
    payload: dict = Body(default={})
):
    """Revert episode card back to Plex's native auto-generated video frame."""
    force_live = payload.get("force_live", False)
    try:
        res = sync_mgr.revert_episode_card(
            show_rating_key=rating_key,
            season_number=season_number,
            episode_number=episode_number,
            force_live=force_live
        )
        return res
    except Exception as e:
        logger.error(f"Failed to revert card for S{season_number}E{episode_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shows/{rating_key}/revert-all")
def revert_all_cards_to_native(
    rating_key: str,
    payload: dict = Body(default={})
):
    """Revert all episode cards for a show back to Plex's native video frames."""
    force_live = payload.get("force_live", False)
    try:
        res = sync_mgr.revert_show_cards(
            show_rating_key=rating_key,
            force_live=force_live
        )
        return res
    except Exception as e:
        logger.error(f"Failed to revert all cards for show {rating_key}: {e}", exc_info=True)
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
