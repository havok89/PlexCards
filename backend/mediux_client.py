import logging
import re
import time
import requests
from typing import List, Dict, Optional, Any, Set, Tuple

logger = logging.getLogger(__name__)

class MediuxClient:
    BASE_URL = "https://mediux.pro"
    ASSET_BASE = "https://api.mediux.pro/assets"

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        self._cache: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
        self._ttl = 600  # 10 minutes cache

    def get_show_sets(self, tmdb_id: int) -> List[Dict[str, Any]]:
        """Fetch all sets for a given TMDb show ID from MediUX (with in-memory caching)."""
        now = time.time()
        if tmdb_id in self._cache:
            cached_time, cached_sets = self._cache[tmdb_id]
            if now - cached_time < self._ttl:
                return cached_sets

        url = f"{self.BASE_URL}/shows/{tmdb_id}"
        try:
            r = requests.get(url, headers=self.headers, timeout=12)
            if r.status_code != 200:
                logger.warning(f"MediUX returned status {r.status_code} for show {tmdb_id}")
                return []
            
            parsed_sets = self._parse_show_page(r.text)
            self._cache[tmdb_id] = (now, parsed_sets)
            return parsed_sets
        except Exception as e:
            logger.error(f"Failed to fetch MediUX data for TMDb {tmdb_id}: {e}")
            return []

    def _parse_show_page(self, html: str) -> List[Dict[str, Any]]:
        """Extract sets and title cards from Next.js payload."""
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
        if not chunks:
            return []
            
        combined = "".join(chunks).replace('\\"', '"').replace('\\\\', '\\')
        
        sets_dict: Dict[str, Dict[str, Any]] = {}
        
        # Match set headers
        # e.g., {"id":"32089","set_name":"Alien: Earth (2025) Set", ... "username":"tallinex", ...}
        for m in re.finditer(r'\{"id":"(\d+)","set_name":"([^"]+)"', combined):
            s_id, s_name = m.group(1), m.group(2)
            if s_id not in sets_dict:
                snippet = combined[m.start(): m.start() + 1000]
                user_match = re.search(r'"username":"([^"]+)"', snippet)
                user = user_match.group(1) if user_match else "Unknown"
                date_match = re.search(r'"date_updated":"([^"]+)"', snippet)
                date_updated = date_match.group(1) if date_match else ""
                
                sets_dict[s_id] = {
                    "id": s_id,
                    "set_name": s_name,
                    "creator": user,
                    "date_updated": date_updated,
                    "set_url": f"{self.BASE_URL}/sets/{s_id}",
                    "title_cards": {}, # "s_e" -> url
                    "season_posters": {}, # "season_num" -> url
                    "seasons_covered": set(),
                    "poster_url": None,
                    "backdrop_url": None
                }

        # Extract show name from payload to filter out franchise boxset sets belonging to other shows
        show_m = re.search(r'"show":\{"id":"\d+","name":"([^"]+)"', combined)
        clean_show = re.sub(r'[^a-z0-9]', '', show_m.group(1).lower()) if show_m else ''

        # Match files inside sets
        # Handles nested JSON inside set_id (e.g. cardCheck:[{"id":"..."}], posterCheck:[...])
        file_pattern = re.compile(
            r'\{"set_id":\{"id":"([^"]+)".*?\},"id":"([a-f0-9\-]+)","filename_disk":"[^"]+","title":"([^"]+)","fileType":"([^"]+)"'
        )
        
        for m in file_pattern.finditer(combined):
            s_id, file_id, title, file_type = m.groups()
            
            if file_type == "title_card":
                # Ensure title card belongs to this show if show name is known
                clean_title = re.sub(r'[^a-z0-9]', '', title.lower())
                if clean_show and clean_show not in clean_title and clean_title not in clean_show:
                    continue

                if s_id not in sets_dict:
                    sets_dict[s_id] = {
                        "id": s_id,
                        "set_name": title.split(" - ")[0] if " - " in title else title,
                        "creator": "Unknown",
                        "date_updated": "",
                        "set_url": f"{self.BASE_URL}/sets/{s_id}",
                        "title_cards": {},
                        "season_posters": {},
                        "seasons_covered": set(),
                        "poster_url": None,
                        "backdrop_url": None
                    }
                
                asset_url = f"{self.ASSET_BASE}/{file_id}"
                # Parse Season and Episode from title (e.g., "... - S1 E1" or "S02E05")
                ep_match = re.search(r'S(\d+)\s*E(\d+)', title, re.IGNORECASE)
                if ep_match:
                    season_num = int(ep_match.group(1))
                    episode_num = int(ep_match.group(2))
                    sets_dict[s_id]["title_cards"][f"{season_num}_{episode_num}"] = asset_url
                    sets_dict[s_id]["seasons_covered"].add(season_num)
            elif file_type == "poster":
                clean_title = re.sub(r'[^a-z0-9]', '', title.lower())
                if clean_show and clean_show not in clean_title and clean_title not in clean_show:
                    continue

                if s_id not in sets_dict:
                    sets_dict[s_id] = {
                        "id": s_id,
                        "set_name": title.split(" - ")[0] if " - " in title else title,
                        "creator": "Unknown",
                        "date_updated": "",
                        "set_url": f"{self.BASE_URL}/sets/{s_id}",
                        "title_cards": {},
                        "season_posters": {},
                        "seasons_covered": set(),
                        "poster_url": None,
                        "backdrop_url": None
                    }

                asset_url = f"{self.ASSET_BASE}/{file_id}"
                season_match = re.search(r'-\s*Season\s*(\d+)', title, re.IGNORECASE)
                if season_match:
                    s_num = int(season_match.group(1))
                    sets_dict[s_id]["season_posters"][str(s_num)] = asset_url
                elif not sets_dict[s_id]["poster_url"]:
                    sets_dict[s_id]["poster_url"] = asset_url
            elif s_id in sets_dict:
                asset_url = f"{self.ASSET_BASE}/{file_id}"
                if file_type == "backdrop" and not sets_dict[s_id]["backdrop_url"]:
                    sets_dict[s_id]["backdrop_url"] = asset_url

        # Format results
        results = []
        for s_id, s_data in sets_dict.items():
            if s_data["title_cards"]: # Only return sets that actually contain title cards
                s_data["total_cards"] = len(s_data["title_cards"])
                s_data["seasons_covered"] = sorted(list(s_data["seasons_covered"]))
                results.append(s_data)

        # Sort by total cards count descending
        results.sort(key=lambda x: x["total_cards"], reverse=True)
        return results

    def find_best_matching_set(
        self,
        tmdb_id: int,
        required_seasons: List[int],
        preferred_creators: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find the best set that covers seasons, prioritizing preferred creators if configured."""
        sets = self.get_show_sets(tmdb_id)
        if not sets:
            return None

        req_set = set(s for s in required_seasons if s > 0)  # ignore specials
        clean_preferred = [c.strip().lower() for c in (preferred_creators or []) if c.strip()]

        def get_creator_rank(creator_name: str) -> int:
            if not clean_preferred or not creator_name:
                return 999
            c_low = creator_name.strip().lower()
            for idx, pref in enumerate(clean_preferred):
                if c_low == pref:
                    return idx
            return 999

        # If user has preferred creators, evaluate their sets first
        if clean_preferred:
            pref_matches = [s for s in sets if get_creator_rank(s.get("creator", "")) < 999]
            if pref_matches:
                # Rank by preference index, then coverage, then total cards
                pref_matches.sort(key=lambda s: (
                    get_creator_rank(s.get("creator", "")),
                    -len(req_set.intersection(set(s.get("seasons_covered", [])))),
                    -s.get("total_cards", 0)
                ))

                # If any preferred set covers 100% of required seasons, choose it!
                for s in pref_matches:
                    covered = set(s.get("seasons_covered", []))
                    if not req_set or req_set.issubset(covered):
                        logger.info(f"⭐ Found 100% matching preferred creator set {s['id']} by {s['creator']} for TMDb {tmdb_id}")
                        return s

                # Otherwise, if it covers at least 1 season (or if no required seasons specified), pick the best preferred set
                if not req_set or any(req_set.intersection(set(s.get("seasons_covered", []))) for s in pref_matches):
                    logger.info(f"⭐ Using best available preferred creator set {pref_matches[0]['id']} by {pref_matches[0]['creator']} for TMDb {tmdb_id}")
                    return pref_matches[0]

        if not req_set:
            return sets[0]

        # First pass: find sets that cover 100% of required seasons
        for s in sets:
            covered = set(s["seasons_covered"])
            if req_set.issubset(covered):
                logger.info(f"Found 100% season matching set {s['id']} by {s['creator']} for TMDb {tmdb_id}")
                return s

        # Fallback: set with the highest number of covered seasons
        sets.sort(key=lambda s: len(req_set.intersection(set(s["seasons_covered"]))), reverse=True)
        return sets[0]

