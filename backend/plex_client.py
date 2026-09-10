import logging
import re
from typing import List, Dict, Optional, Any
from plexapi.server import PlexServer
from backend.config import PLEX_URL, PLEX_TOKEN, PLEX_TV_LIBRARY

logger = logging.getLogger(__name__)

class PlexClient:
    def __init__(self, base_url: str = PLEX_URL, token: str = PLEX_TOKEN):
        self.base_url = base_url
        self.token = token
        self._server: Optional[PlexServer] = None

    @property
    def server(self) -> PlexServer:
        if not self._server:
            if not self.token:
                raise ValueError("PLEX_TOKEN is not configured in .env")
            self._server = PlexServer(self.base_url, self.token)
        return self._server

    def get_tv_section(self):
        """Find the TV shows library case-insensitively."""
        server = self.server
        sections = server.library.sections()
        
        # Exact or case-insensitive match
        for s in sections:
            if s.title.lower() == PLEX_TV_LIBRARY.lower() and s.type == "show":
                return s
        
        # Fallback to any library of type 'show'
        for s in sections:
            if s.type == "show":
                return s
                
        raise ValueError(f"No TV show library found matching '{PLEX_TV_LIBRARY}'. Available: {[s.title for s in sections]}")

    def get_all_shows(self) -> List[Dict[str, Any]]:
        """Retrieve all shows from Plex with their TMDb IDs."""
        tv_section = self.get_tv_section()
        plex_shows = tv_section.all()
        
        result = []
        for show in plex_shows:
            tmdb_id = self._extract_tmdb_id(show)
            poster_url = show.posterUrl if hasattr(show, 'posterUrl') else None
            art_url = show.artUrl if hasattr(show, 'artUrl') else None
            
            # Count seasons excluding Specials (season 0) for core coverage
            seasons = [s for s in show.seasons() if s.seasonNumber > 0]
            total_episodes = sum(len(s.episodes()) for s in seasons)
            
            result.append({
                "rating_key": str(show.ratingKey),
                "title": show.title,
                "year": show.year,
                "tmdb_id": tmdb_id,
                "poster_url": poster_url,
                "backdrop_url": art_url,
                "total_seasons": len(seasons),
                "total_episodes": total_episodes,
                "seasons_list": [s.seasonNumber for s in seasons]
            })
            
        return result

    def get_show_episodes(self, show_rating_key: str) -> List[Dict[str, Any]]:
        """Fetch all episodes for a show from Plex."""
        server = self.server
        show = server.fetchItem(int(show_rating_key))
        episodes_data = []
        
        for ep in show.episodes():
            if ep.seasonNumber == 0:
                continue # Skip specials for standard title card workflows
            
            thumb_url = ep.thumbUrl if hasattr(ep, 'thumbUrl') else None
            episodes_data.append({
                "rating_key": str(ep.ratingKey),
                "season_number": ep.seasonNumber,
                "episode_number": ep.episodeNumber,
                "title": ep.title,
                "thumb_url": thumb_url
            })
        return episodes_data

    def upload_episode_card(self, episode_rating_key: str, file_path_or_url: str, force_live: bool = False):
        """Upload a title card image to a Plex episode (gated by TEST_MODE unless force_live=True)."""
        from backend.config import TEST_MODE
        if TEST_MODE and not force_live:
            logger.info(f"🧪 [TEST MODE] Skipped upload to Plex for episode ID {episode_rating_key}. (Test mode active)")
            return

        server = self.server
        episode = server.fetchItem(int(episode_rating_key))
        
        if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
            episode.uploadPoster(url=file_path_or_url)
        else:
            episode.uploadPoster(filepath=file_path_or_url)
        logger.info(f"✓ Uploaded title card to Plex for episode {episode.title} (S{episode.seasonNumber:02d}E{episode.episodeNumber:02d})")

    def get_show_seasons(self, show_rating_key: str) -> List[Dict[str, Any]]:
        """Fetch all seasons for a show from Plex."""
        server = self.server
        show = server.fetchItem(int(show_rating_key))
        return [
            {
                "rating_key": str(s.ratingKey),
                "season_number": s.seasonNumber,
                "title": s.title
            }
            for s in show.seasons()
        ]

    def upload_season_poster(self, season_rating_key: str, file_path_or_url: str, force_live: bool = False):
        """Upload a season poster to Plex (gated by TEST_MODE unless force_live=True)."""
        from backend.config import TEST_MODE
        if TEST_MODE and not force_live:
            logger.info(f"🧪 [TEST MODE] Skipped upload of season poster to Plex for season ID {season_rating_key}. (Test mode active)")
            return

        server = self.server
        season = server.fetchItem(int(season_rating_key))
        if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
            season.uploadPoster(url=file_path_or_url)
        else:
            season.uploadPoster(filepath=file_path_or_url)
        logger.info(f"✓ Uploaded season poster to Plex for {season.parentTitle} - Season {season.seasonNumber}")

    def _extract_tmdb_id(self, item) -> Optional[int]:
        """Extract TMDb ID from Plex GUIDs (e.g., 'tmdb://103516')."""
        if hasattr(item, 'guids'):
            for g in item.guids:
                if g.id.startswith('tmdb://'):
                    try:
                        return int(g.id.replace('tmdb://', ''))
                    except ValueError:
                        pass
                        
        # Fallback check item.guid
        if hasattr(item, 'guid'):
            match = re.search(r'tmdb://(\d+)', item.guid)
            if match:
                return int(match.group(1))
        return None

    def fix_match_show(self, rating_key: str, title: Optional[str] = None, year: Optional[int] = None) -> Dict[str, Any]:
        """Search Plex agent matches for a show and apply the top match to fix matching in Plex."""
        server = self.server
        show = server.fetchItem(int(rating_key))
        search_title = title or show.title
        search_year = year or show.year
        
        matches = show.matches(title=search_title, year=search_year)
        if not matches and search_year:
            matches = show.matches(title=search_title)

        if not matches:
            return {"success": False, "message": f"No matches found in Plex for '{search_title}'"}

        best_match = matches[0]
        logger.info(f"Applying Plex fixMatch for '{show.title}' -> '{best_match.name}' ({best_match.year}, guid={best_match.guid})")
        show.fixMatch(best_match)

        return {
            "success": True,
            "matched_title": best_match.name,
            "matched_year": best_match.year,
            "matched_guid": best_match.guid,
            "message": f"Successfully matched '{best_match.name}' ({best_match.year}) in Plex."
        }

