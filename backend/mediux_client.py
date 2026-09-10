import logging
import re
import requests
from typing import List, Dict, Optional, Any, Set

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

    def get_show_sets(self, tmdb_id: int) -> List[Dict[str, Any]]:
        """Fetch all sets for a given TMDb show ID from MediUX."""
        url = f"{self.BASE_URL}/shows/{tmdb_id}"
        try:
            r = requests.get(url, headers=self.headers, timeout=12)
            if r.status_code != 200:
                logger.warning(f"MediUX returned status {r.status_code} for show {tmdb_id}")
                return []
            
            return self._parse_show_page(r.text)
        except Exception as e:
            logger.error(f"Failed to fetch MediUX data for TMDb {tmdb_id}: {e}")
            return []

    def _parse_show_page(self, html: str) -> List[Dict[str, Any]]:
        """Extract sets and title cards from Next.js payload."""
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html)
        if not chunks:
            return []
            
        combined = "".join(chunks).replace('\\"', '"').replace('\\\\', '\\')
        
        # Locate the "sets":[ ... ] array
        sets_marker = '"sets":['
        idx = combined.find(sets_marker)
        if idx == -1:
            return []

        # Find individual sets by extracting { "id": "...", "set_name": ... } blocks
        # We can extract the file items directly
        # Pattern for title_card file items
        # Example: {"id":"...", "filename_disk":"...", "title":"... - S1 E1", "fileType":"title_card", ...}
        
        # Let's extract all sets and their files
        sets_dict: Dict[str, Dict[str, Any]] = {}
        
        # Match set headers
        set_headers = re.findall(
            r'\{"id":"([^"]+)","set_name":"([^"]+)"(?:,[^}]*?"date_updated":"([^"]*)")?(?:,[^}]*?"username":"([^"]*)")?',
            combined
        )
        for s_id, s_name, updated, user in set_headers:
            if s_id not in sets_dict:
                sets_dict[s_id] = {
                    "id": s_id,
                    "set_name": s_name,
                    "creator": user or "Unknown",
                    "date_updated": updated or "",
                    "set_url": f"{self.BASE_URL}/sets/{s_id}",
                    "title_cards": {}, # (season, episode) -> url
                    "seasons_covered": set(),
                    "poster_url": None,
                    "backdrop_url": None
                }

        # Match files inside sets
        # Example pattern: {"set_id":{"id":"404"...},"id":"bfe356bb...","filename_disk":"...","title":"... - S1 E1","fileType":"title_card"...}
        file_matches = re.finditer(
            r'\{"set_id":\{"id":"([^"]+)"[^{}]*\},"id":"([^"]+)","filename_disk":"[^"]+","title":"([^"]+)","fileType":"([^"]+)"',
            combined
        )
        
        for m in file_matches:
            s_id, file_id, title, file_type = m.groups()
            if s_id not in sets_dict:
                sets_dict[s_id] = {
                    "id": s_id,
                    "set_name": title.split(" - ")[0] if " - " in title else title,
                    "creator": "Unknown",
                    "date_updated": "",
                    "set_url": f"{self.BASE_URL}/sets/{s_id}",
                    "title_cards": {},
                    "seasons_covered": set(),
                    "poster_url": None,
                    "backdrop_url": None
                }
            
            asset_url = f"{self.ASSET_BASE}/{file_id}"
            
            if file_type == "title_card":
                # Parse Season and Episode from title (e.g., "... - S1 E1" or "S02E05")
                ep_match = re.search(r'S(\d+)\s*E(\d+)', title, re.IGNORECASE)
                if ep_match:
                    season_num = int(ep_match.group(1))
                    episode_num = int(ep_match.group(2))
                    sets_dict[s_id]["title_cards"][(season_num, episode_num)] = asset_url
                    sets_dict[s_id]["seasons_covered"].add(season_num)
            elif file_type == "poster" and not sets_dict[s_id]["poster_url"]:
                sets_dict[s_id]["poster_url"] = asset_url
            elif file_type == "backdrop" and not sets_dict[s_id]["backdrop_url"]:
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

    def find_best_matching_set(self, tmdb_id: int, required_seasons: List[int]) -> Optional[Dict[str, Any]]:
        """Find the first set that covers all the seasons present in the user's Plex library."""
        sets = self.get_show_sets(tmdb_id)
        if not sets:
            return None

        req_set = set(s for s in required_seasons if s > 0) # ignore specials
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
