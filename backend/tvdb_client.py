import logging
import json
import time
import requests
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from backend.config import TVDB_API_KEY, TVDB_PIN, STILLS_DIR, LOGOS_DIR, CACHE_DIR

logger = logging.getLogger(__name__)

class TVDbClient:
    BASE_URL = "https://api4.thetvdb.com/v4"
    TOKEN_CACHE_FILE = CACHE_DIR / "tvdb_token.json"

    def __init__(self, api_key: str = TVDB_API_KEY, pin: str = TVDB_PIN):
        self.api_key = api_key
        self.pin = pin
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._series_episodes_cache: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
        self._cache_ttl = 3600  # 1 hour cache for episode lists

    @property
    def is_configured(self) -> bool:
        """Check if TVDB API key is present."""
        return bool(self.api_key and self.api_key.strip())

    def _get_auth_token(self, force_refresh: bool = False) -> Optional[str]:
        """Obtain or restore JWT Bearer token from TVDB v4."""
        if not self.is_configured:
            return None

        now = time.time()
        if not force_refresh and self._token and now < (self._token_expires_at - 300):
            return self._token

        # Check disk cache
        if not force_refresh and self.TOKEN_CACHE_FILE.exists():
            try:
                with open(self.TOKEN_CACHE_FILE, "r") as f:
                    data = json.load(f)
                token = data.get("token")
                expires_at = data.get("expires_at", 0)
                if token and now < (expires_at - 300):
                    self._token = token
                    self._token_expires_at = expires_at
                    return self._token
            except Exception:
                pass

        # Perform login request
        login_url = f"{self.BASE_URL}/login"
        payload: Dict[str, str] = {"apikey": self.api_key.strip()}
        if self.pin and self.pin.strip():
            payload["pin"] = self.pin.strip()

        try:
            r = requests.post(login_url, json=payload, headers={"Content-Type": "application/json"}, timeout=12)
            if r.status_code == 200:
                res_data = r.json().get("data", {})
                token = res_data.get("token")
                if token:
                    self._token = token
                    # TVDB tokens are valid for ~30 days (2,592,000 seconds); default to 28 days
                    self._token_expires_at = now + 2419200
                    try:
                        with open(self.TOKEN_CACHE_FILE, "w") as f:
                            json.dump({"token": self._token, "expires_at": self._token_expires_at}, f)
                    except Exception as e:
                        logger.warning(f"Could not write TVDB token cache: {e}")
                    logger.info("Successfully authenticated with TheTVDB API v4")
                    return self._token
            logger.error(f"TVDB login failed with status {r.status_code}: {r.text}")
        except Exception as e:
            logger.error(f"Error authenticating with TheTVDB v4: {e}")
        return None

    def _headers(self) -> Dict[str, str]:
        token = self._get_auth_token()
        headers = {
            "Accept": "application/json",
            "User-Agent": "PlexCards/1.0"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Helper to send authenticated requests with automatic retry on 401 token expiry."""
        if not self.is_configured:
            return None

        url = f"{self.BASE_URL}{endpoint}"
        try:
            r = requests.request(method, url, headers=self._headers(), params=params, timeout=12)
            if r.status_code == 401:
                # Token may have expired, refresh once
                logger.info("TVDB returned 401 Unauthorized; refreshing token...")
                token = self._get_auth_token(force_refresh=True)
                if token:
                    r = requests.request(method, url, headers=self._headers(), params=params, timeout=12)
            if r.status_code == 200:
                return r.json()
            else:
                logger.warning(f"TVDB request {endpoint} returned status {r.status_code}")
        except Exception as e:
            logger.error(f"TVDB request {endpoint} failed: {e}")
        return None

    def get_series_extended(self, tvdb_id: int) -> Optional[Dict[str, Any]]:
        """Fetch full series metadata including artworks and remote IDs."""
        res = self._request("GET", f"/series/{tvdb_id}/extended")
        if res and res.get("status") == "success":
            return res.get("data")
        return None

    def resolve_tmdb_id(self, tvdb_id: int) -> Optional[int]:
        """Extract TMDb ID from TVDB remote IDs mapping."""
        series_data = self.get_series_extended(tvdb_id)
        if not series_data:
            return None

        remote_ids = series_data.get("remoteIds", []) or []
        for item in remote_ids:
            source = (item.get("sourceName") or "").lower()
            item_id = str(item.get("id") or "")
            if ("themoviedb" in source or "tmdb" in source) and item_id.isdigit():
                try:
                    return int(item_id)
                except ValueError:
                    pass
        return None

    def resolve_tvdb_id_from_remote(self, remote_id: str) -> Optional[int]:
        """Lookup TVDB series ID using remote ID (e.g. IMDb ID 'tt...' or TMDb ID)."""
        res = self._request("GET", f"/search/remoteid/{remote_id}")
        if res and res.get("status") == "success":
            data = res.get("data", [])
            for entry in data:
                series_info = entry.get("series")
                if series_info and series_info.get("id"):
                    return int(series_info["id"])
                if entry.get("type") == "series" and entry.get("id"):
                    return int(entry["id"])
        return None

    def get_series_status(self, tvdb_id: int) -> Optional[str]:
        """Fetch series broadcast status (e.g. 'Continuing', 'Ended') from TVDB."""
        series_data = self.get_series_extended(tvdb_id)
        if series_data:
            st = series_data.get("status")
            if isinstance(st, dict):
                return st.get("name")
            elif isinstance(st, str):
                return st
        return None

    def get_series_episodes(self, tvdb_id: int, season_type: str = "default") -> List[Dict[str, Any]]:
        """Fetch episodes for a series (cached in memory for 1 hour)."""
        now = time.time()
        if tvdb_id in self._series_episodes_cache:
            cache_time, cached_episodes = self._series_episodes_cache[tvdb_id]
            if now - cache_time < self._cache_ttl:
                return cached_episodes

        all_episodes = []
        page = 0
        while True:
            res = self._request("GET", f"/series/{tvdb_id}/episodes/{season_type}", params={"page": page})
            if not res or res.get("status") != "success":
                break

            data = res.get("data", {})
            episodes = data.get("episodes", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            if not episodes:
                break

            all_episodes.extend(episodes)
            links = res.get("links", {})
            if not links.get("next") or page >= 10:
                break
            page += 1

        if all_episodes:
            self._series_episodes_cache[tvdb_id] = (now, all_episodes)
        return all_episodes

    def get_episode_info(self, tvdb_id: int, season_number: int, episode_number: int) -> Optional[Dict[str, Any]]:
        """Find a specific episode by season and episode number."""
        episodes = self.get_series_episodes(tvdb_id)
        for ep in episodes:
            if ep.get("seasonNumber") == season_number and ep.get("number") == episode_number:
                return ep
        return None

    def get_episode_still(
        self,
        tvdb_id: int,
        season_number: int,
        episode_number: int,
        specific_still_url: Optional[str] = None
    ) -> Optional[Path]:
        """Fetch and cache high-res episode screencap from TheTVDB."""
        if not self.is_configured or not tvdb_id:
            return None

        cache_filename = STILLS_DIR / f"tvdb_{tvdb_id}_S{season_number:02d}E{episode_number:02d}.jpg"
        if not specific_still_url and cache_filename.exists():
            return cache_filename

        target_url = specific_still_url
        if not target_url:
            ep_info = self.get_episode_info(tvdb_id, season_number, episode_number)
            if ep_info and ep_info.get("image"):
                target_url = ep_info["image"]

        if not target_url:
            return None

        if specific_still_url:
            clean_name = target_url.split("/")[-1].replace("?", "_")
            if not clean_name.lower().endswith((".jpg", ".jpeg", ".png")):
                clean_name += ".jpg"
            cache_filename = STILLS_DIR / f"tvdb_{tvdb_id}_custom_{clean_name}"
            if cache_filename.exists():
                return cache_filename

        try:
            r = requests.get(target_url, headers={"User-Agent": "PlexCards/1.0"}, timeout=15)
            if r.status_code == 200:
                with open(cache_filename, "wb") as f:
                    f.write(r.content)
                return cache_filename
            else:
                logger.warning(f"Failed to download TVDB still from {target_url} (HTTP {r.status_code})")
        except Exception as e:
            logger.error(f"Error fetching TVDB still for {tvdb_id} S{season_number}E{episode_number}: {e}")
        return None

    def get_episode_stills_list(
        self,
        tvdb_id: int,
        season_number: int,
        episode_number: int
    ) -> List[Dict[str, Any]]:
        """Fetch candidate stills for an episode from TVDB."""
        if not self.is_configured or not tvdb_id:
            return []

        ep_info = self.get_episode_info(tvdb_id, season_number, episode_number)
        if not ep_info:
            return []

        stills = []
        image_url = ep_info.get("image")
        if image_url:
            stills.append({
                "file_path": image_url,
                "thumb_url": image_url,
                "full_url": image_url,
                "width": 1920,
                "height": 1080,
                "aspect_ratio": 1.78,
                "is_16_9": True,
                "vote_average": 5.0,
                "vote_count": 1,
                "quality_score": 15.0,
                "is_top_pick": True,
                "provider": "tvdb",
                "title": ep_info.get("name", f"Episode {episode_number}")
            })
        return stills

    def get_show_logo(self, tvdb_id: int) -> Optional[Path]:
        """Fetch and cache transparent series clearlogo from TVDB."""
        if not self.is_configured or not tvdb_id:
            return None

        cache_filename = LOGOS_DIR / f"tvdb_{tvdb_id}.png"
        if cache_filename.exists():
            return cache_filename

        series_data = self.get_series_extended(tvdb_id)
        if not series_data:
            return None

        artworks = series_data.get("artworks", []) or []
        logo_url = None
        for art in artworks:
            art_type = art.get("type")
            art_image = art.get("image", "")
            if (art_type == 23 or "clearlogo" in str(art_image).lower()) and art_image.endswith(".png"):
                if art.get("language") == "eng":
                    logo_url = art_image
                    break
                if not logo_url:
                    logo_url = art_image

        if logo_url:
            try:
                r = requests.get(logo_url, headers={"User-Agent": "PlexCards/1.0"}, timeout=15)
                if r.status_code == 200:
                    with open(cache_filename, "wb") as f:
                        f.write(r.content)
                    return cache_filename
            except Exception as e:
                logger.warning(f"Failed to download TVDB logo for {tvdb_id}: {e}")
        return None

    def search_shows(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search TV shows on TVDB by title."""
        if not self.is_configured or not query:
            return []

        params: Dict[str, Any] = {
            "query": query,
            "type": "series"
        }
        if year:
            params["year"] = str(year)

        res = self._request("GET", "/search", params=params)
        if not res or res.get("status") != "success":
            return []

        results = []
        for item in res.get("data", []):
            year_val = None
            y_str = str(item.get("year") or "")
            if y_str.isdigit():
                year_val = int(y_str)

            raw_id = item.get("tvdb_id") or item.get("id")
            if not raw_id:
                continue

            try:
                tvdb_id = int(raw_id)
            except (ValueError, TypeError):
                continue

            results.append({
                "tvdb_id": tvdb_id,
                "name": item.get("name"),
                "year": year_val,
                "overview": item.get("overview"),
                "poster_url": item.get("image_url"),
                "status": item.get("status")
            })
        return results
