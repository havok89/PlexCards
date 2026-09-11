import logging
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path
from backend.config import TMDB_API_KEY, STILLS_DIR, LOGOS_DIR

logger = logging.getLogger(__name__)

class TMDbClient:
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p/original"
    POSTER_BASE = "https://image.tmdb.org/t/p/w500"

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
                # Find clean PNG logo if available, prioritizing English
                logos = data.get("images", {}).get("logos", [])
                logo_path = None
                for l in logos:
                    if l.get("file_path", "").endswith(".png") and l.get("iso_639_1") == "en":
                        logo_path = l.get("file_path")
                        break
                if not logo_path:
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
                    "poster_url": f"{self.POSTER_BASE}{data.get('poster_path')}" if data.get('poster_path') else None,
                    "logo_url": f"{self.IMAGE_BASE}{logo_path}" if logo_path else None,
                    "status": data.get("status", "Returning Series"),
                    "in_production": data.get("in_production", True)
                }
        except Exception as e:
            logger.error(f"Error fetching TMDb show {tmdb_id}: {e}")
        return None

    def get_show_logo(self, tmdb_id: int) -> Optional[Path]:
        """Fetch and cache transparent show logo PNG."""
        if not self.api_key or not tmdb_id:
            return None

        cache_filename = LOGOS_DIR / f"{tmdb_id}.png"
        if cache_filename.exists():
            return cache_filename

        details = self.get_show_details(tmdb_id)
        if details and details.get("logo_url"):
            try:
                img_res = requests.get(details["logo_url"], timeout=15)
                if img_res.status_code == 200:
                    with open(cache_filename, "wb") as f:
                        f.write(img_res.content)
                    return cache_filename
            except Exception as e:
                logger.warning(f"Failed to download logo for {tmdb_id}: {e}")
        return None

    def get_episode_still(
        self,
        tmdb_id: int,
        season_number: int,
        episode_number: int,
        specific_still_path: Optional[str] = None
    ) -> Optional[Path]:
        """Fetch and cache high-res episode backdrop still image.
        Supports fetching a specific candidate still_path if requested.
        """
        if not self.api_key or not tmdb_id:
            return None

        if specific_still_path:
            clean_name = specific_still_path.strip("/").replace("/", "_")
            if not clean_name.lower().endswith((".jpg", ".jpeg", ".png")):
                clean_name += ".jpg"
            cache_filename = STILLS_DIR / f"{tmdb_id}_custom_{clean_name}"
            if cache_filename.exists():
                return cache_filename
            try:
                img_url = f"{self.IMAGE_BASE}{specific_still_path}"
                img_res = requests.get(img_url, timeout=15)
                if img_res.status_code == 200:
                    with open(cache_filename, "wb") as f:
                        f.write(img_res.content)
                    return cache_filename
            except Exception as e:
                logger.error(f"Error fetching specific still {specific_still_path} for {tmdb_id}: {e}")
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

    def get_episode_stills_list(
        self,
        tmdb_id: int,
        season_number: int,
        episode_number: int
    ) -> List[Dict[str, Any]]:
        """Fetch all candidate backdrop stills for an episode from TMDb, sorted by quality score."""
        import math
        if not self.api_key or not tmdb_id:
            return []

        url = f"{self.BASE_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/images?api_key={self.api_key}"
        results = []
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                stills = r.json().get("stills", [])
                for s in stills:
                    file_path = s.get("file_path")
                    if not file_path:
                        continue
                    w = s.get("width", 1920) or 1920
                    h = s.get("height", 1080) or 1080
                    aspect = (w / h) if h > 0 else 1.778
                    is_16_9 = abs(aspect - 1.778) < 0.08
                    vote_avg = float(s.get("vote_average", 0.0) or 0.0)
                    vote_cnt = int(s.get("vote_count", 0) or 0)

                    # Community score formula: higher community ratings + log count + resolution + 16:9 preference
                    score = (vote_avg * math.log2(vote_cnt + 2))
                    if is_16_9:
                        score *= 1.25
                    if w >= 1920:
                        score *= 1.15

                    results.append({
                        "file_path": file_path,
                        "thumb_url": f"https://image.tmdb.org/t/p/w300{file_path}",
                        "full_url": f"{self.IMAGE_BASE}{file_path}",
                        "width": w,
                        "height": h,
                        "aspect_ratio": round(aspect, 2),
                        "is_16_9": is_16_9,
                        "vote_average": round(vote_avg, 1),
                        "vote_count": vote_cnt,
                        "quality_score": round(score, 2)
                    })

                # Sort by quality score descending
                results.sort(key=lambda x: x["quality_score"], reverse=True)
                if results:
                    results[0]["is_top_pick"] = True
                return results
        except Exception as e:
            logger.error(f"Error fetching candidate stills for {tmdb_id} S{season_number}E{episode_number}: {e}")

        # Fallback: check single episode info for default still_path
        try:
            ep_url = f"{self.BASE_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}?api_key={self.api_key}"
            er = requests.get(ep_url, timeout=10)
            if er.status_code == 200:
                data = er.json()
                sp = data.get("still_path")
                if sp:
                    return [{
                        "file_path": sp,
                        "thumb_url": f"https://image.tmdb.org/t/p/w300{sp}",
                        "full_url": f"{self.IMAGE_BASE}{sp}",
                        "width": 1920,
                        "height": 1080,
                        "aspect_ratio": 1.78,
                        "is_16_9": True,
                        "vote_average": 5.0,
                        "vote_count": 1,
                        "quality_score": 10.0,
                        "is_top_pick": True
                    }]
        except Exception:
            pass

        return []

    def search_shows(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search TV shows on TMDb by title and optional release/air year."""
        if not self.api_key or not query:
            return []

        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
        }
        if year:
            params["first_air_date_year"] = year

        url = f"{self.BASE_URL}/search/tv"
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                results = []
                for item in data.get("results", []):
                    air_date = item.get("first_air_date") or ""
                    release_year = int(air_date[:4]) if air_date and air_date[:4].isdigit() else None
                    results.append({
                        "tmdb_id": item["id"],
                        "name": item.get("name"),
                        "year": release_year,
                        "overview": item.get("overview"),
                        "poster_url": f"{self.IMAGE_BASE}{item.get('poster_path')}" if item.get("poster_path") else None,
                        "backdrop_url": f"{self.IMAGE_BASE}{item.get('backdrop_path')}" if item.get("backdrop_path") else None,
                    })
                return results
        except Exception as e:
            logger.error(f"Error searching TMDb shows for '{query}': {e}")
        return []

