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

# TMDb
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")

# MediUX
MEDIUX_API_TOKEN = os.getenv("MEDIUX_API_TOKEN", "")

# AI / LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Server & Schedules
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
POLL_INTERVAL_HOURS = int(os.getenv("POLL_INTERVAL_HOURS", "12"))

# Safety Gate: Test / Dry Run Mode (Default is True to prevent accidental Plex overwrites)
TEST_MODE = os.getenv("TEST_MODE", "true").lower() in ("true", "1", "yes")

# Directories
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "cache"
FONTS_DIR = BASE_DIR / "cache" / "fonts"
STILLS_DIR = BASE_DIR / "cache" / "stills"
TEST_OUTPUT_DIR = BASE_DIR / "cache" / "test_output"
PREVIEWS_DIR = BASE_DIR / "cache" / "previews"

for directory in [DATA_DIR, CACHE_DIR, FONTS_DIR, STILLS_DIR, TEST_OUTPUT_DIR, PREVIEWS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "plexposters.db"
