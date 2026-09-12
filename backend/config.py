import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Plex
PLEX_URL = os.getenv("PLEX_URL", "http://localhost:32400").rstrip("/")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")
PLEX_TV_LIBRARY = os.getenv("PLEX_TV_LIBRARY", "TV Shows")
PLEX_MOVIE_LIBRARY = os.getenv("PLEX_MOVIE_LIBRARY", "Movies")

# TMDb
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")

# TheTVDB (TVDB API v4)
TVDB_API_KEY = os.getenv("TVDB_API_KEY", "")
TVDB_PIN = os.getenv("TVDB_PIN", "")
DEFAULT_METADATA_PROVIDER = os.getenv("DEFAULT_METADATA_PROVIDER", "tvdb" if TVDB_API_KEY else "tmdb")

# MediUX
MEDIUX_API_TOKEN = os.getenv("MEDIUX_API_TOKEN", "")

# AI / LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Server & Schedules
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
POLL_INTERVAL_HOURS = int(os.getenv("POLL_INTERVAL_HOURS", "12"))

# Safety Gate: Test / Dry Run Mode (Default is True to prevent accidental Plex overwrites)
TEST_MODE = os.getenv("TEST_MODE", "true").lower() in ("true", "1", "yes")

# Authentication
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() in ("true", "1", "yes")
ALLOWED_USERS = [u.strip().lower() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()]
SECRET_KEY = os.getenv("SECRET_KEY", "")
PLEX_CLIENT_IDENTIFIER = os.getenv("PLEX_CLIENT_IDENTIFIER", "PlexCards-App")

# Directories
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", BASE_DIR / "cache"))
FONTS_DIR = CACHE_DIR / "fonts"
STILLS_DIR = CACHE_DIR / "stills"
TEST_OUTPUT_DIR = CACHE_DIR / "test_output"
PREVIEWS_DIR = CACHE_DIR / "previews"
POSTERS_DIR = CACHE_DIR / "posters"
LOGOS_DIR = CACHE_DIR / "logos"
CUSTOM_FONTS_DIR = Path(os.getenv("CUSTOM_FONTS_DIR", BASE_DIR / "custom_fonts"))

for directory in [DATA_DIR, CACHE_DIR, FONTS_DIR, STILLS_DIR, TEST_OUTPUT_DIR, PREVIEWS_DIR, CUSTOM_FONTS_DIR, POSTERS_DIR, LOGOS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database path (supports existing plexposters.db or new plexcards.db)
legacy_db = DATA_DIR / "plexposters.db"
new_db = DATA_DIR / "plexcards.db"
DB_PATH = legacy_db if (legacy_db.exists() and not new_db.exists()) else new_db
