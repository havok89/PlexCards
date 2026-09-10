import logging
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path
from backend.config import TMDB_API_KEY, STILLS_DIR

logger = logging.getLogger(__name__)

class TMDbClient:
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p/original"

    def __init__(self, api_key: str = TMDB_API_KEY):
        self.api_key = api_key

    def get_show_details(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """Fetch TV show overview, genres, and artwork metadata."""
        if not self.api_key or not tmdb_id:
            return None
        url = f"{self.BASE_URL}/tv/{tmdb_id}?api_key={self.api_key}&append_to_response=images"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Find clean PNG logo if available
                logos = data.get("images", {}).get("logos", [])
                logo_path = None
                for l in logos:
                    if l.get("file_path", "").endswith(".png"):
                        logo_path = l.get("file_path")
                        break
                
                return {
                    "tmdb_id": tmdb_id,
                    "name": data.get("name"),
                    "overview": data.get("overview"),
                    "genres": [g["name"] for g in data.get("genres", [])],
                    "backdrop_url": f"{self.IMAGE_BASE}{data.get('backdrop_path')}" if data.get('backdrop_path') else None,
                    "poster_url": f"{self.IMAGE_BASE}{data.get('poster_path')}" if data.get('poster_path') else None,
                    "logo_url": f"{self.IMAGE_BASE}{logo_path}" if logo_path else None
                }
        except Exception as e:
            logger.error(f"Error fetching TMDb show {tmdb_id}: {e}")
        return None

    def get_episode_still(self, tmdb_id: int, season_number: int, episode_number: int) -> Optional[Path]:
        """Fetch and cache high-res episode backdrop still image."""
        if not self.api_key or not tmdb_id:
            return None

        cache_filename = STILLS_DIR / f"{tmdb_id}_S{season_number:02d}E{episode_number:02d}.jpg"
        if cache_filename.exists():
            return cache_filename

        url = f"{self.BASE_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}?api_key={self.api_key}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                still_path = data.get("still_path")
                if still_path:
                    img_url = f"{self.IMAGE_BASE}{still_path}"
                    img_res = requests.get(img_url, timeout=15)
                    if img_res.status_code == 200:
                        with open(cache_filename, "wb") as f:
                            f.write(img_res.content)
                        return cache_filename
        except Exception as e:
            logger.error(f"Error fetching episode still for {tmdb_id} S{season_number}E{episode_number}: {e}")
        return None
