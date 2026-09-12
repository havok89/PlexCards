import logging
import re
from typing import List, Dict, Optional, Any
from plexapi.server import PlexServer
from backend.config import PLEX_URL, PLEX_TOKEN, PLEX_TV_LIBRARY, PLEX_MOVIE_LIBRARY

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

    def get_tv_sections(self) -> List[Dict[str, Any]]:
        """Find all TV show sections on the Plex server."""
        server = self.server
        sections = server.library.sections()
        return [
            {
                "key": str(s.key),
                "title": s.title,
                "type": s.type
            }
            for s in sections if s.type == "show"
        ]

    def get_movie_sections(self) -> List[Dict[str, Any]]:
        """Find all Movie sections on the Plex server."""
        server = self.server
        sections = server.library.sections()
        return [
            {
                "key": str(s.key),
                "title": s.title,
                "type": "movie"
            }
            for s in sections if s.type == "movie"
        ]

    def get_all_sections(self) -> List[Dict[str, Any]]:
        """Find all TV and Movie sections on the Plex server."""
        server = self.server
        sections = server.library.sections()
        return [
            {
                "key": str(s.key),
                "title": s.title,
                "type": s.type
            }
            for s in sections if s.type in ("show", "movie")
        ]

    def get_movie_section(self, target_library: Optional[str] = None):
        """Find the Movie library case-insensitively or by section key/title."""
        from backend.db import get_setting
        server = self.server
        sections = server.library.sections()
        movie_sections = [s for s in sections if s.type == "movie"]

        if not movie_sections:
            raise ValueError("No Movie library found on Plex server.")

        # 1. Check explicit target_library
        if target_library:
            target_str = str(target_library).strip()
            for s in movie_sections:
                if str(s.key) == target_str or s.title.lower() == target_str.lower():
                    return s

        # 2. Check active_plex_movie_library setting
        active_lib = get_setting("active_plex_movie_library", None)
        if active_lib:
            target_str = str(active_lib).strip()
            for s in movie_sections:
                if str(s.key) == target_str or s.title.lower() == target_str.lower():
                    return s

        # 3. Exact or case-insensitive match on default PLEX_MOVIE_LIBRARY
        for s in movie_sections:
            if s.title.lower() == PLEX_MOVIE_LIBRARY.lower():
                return s

        # 4. Fallback to first available Movie library
        return movie_sections[0]

    def get_tv_section(self, target_library: Optional[str] = None):
        """Find the TV shows library case-insensitively or by section key/title."""
        from backend.db import get_setting
        server = self.server
        sections = server.library.sections()
        tv_sections = [s for s in sections if s.type == "show"]

        if not tv_sections:
            raise ValueError("No TV show library found on Plex server.")

        # 1. Check explicit target_library
        if target_library:
            target_str = str(target_library).strip()
            for s in tv_sections:
                if str(s.key) == target_str or s.title.lower() == target_str.lower():
                    return s

        # 2. Check active_plex_library setting
        active_lib = get_setting("active_plex_library", None)
        if active_lib:
            target_str = str(active_lib).strip()
            for s in tv_sections:
                if str(s.key) == target_str or s.title.lower() == target_str.lower():
                    return s

        # 3. Exact or case-insensitive match on default PLEX_TV_LIBRARY
        for s in tv_sections:
            if s.title.lower() == PLEX_TV_LIBRARY.lower():
                return s

        # 4. Fallback to first available TV library
        return tv_sections[0]

    def get_all_shows(self, target_library: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all shows from Plex with their TMDb IDs."""
        tv_section = self.get_tv_section(target_library=target_library)
        plex_shows = tv_section.all()
        
        result = []
        for show in plex_shows:
            tmdb_id = self._extract_tmdb_id(show)
            tvdb_id = self._extract_tvdb_id(show)
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
                "tvdb_id": tvdb_id,
                "poster_url": poster_url,
                "backdrop_url": art_url,
                "total_seasons": len(seasons),
                "total_episodes": total_episodes,
                "seasons_list": [s.seasonNumber for s in seasons],
                "library_section_id": str(tv_section.key),
                "library_name": tv_section.title
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

    def revert_episode_card(self, episode_rating_key: str, force_live: bool = False):
        """Revert an episode card back to Plex's native auto-generated video frame."""
        from backend.config import TEST_MODE
        if TEST_MODE and not force_live:
            logger.info(f"🧪 [TEST MODE] Skipped reverting episode ID {episode_rating_key} in Plex. (Test mode active)")
            return

        server = self.server
        episode = server.fetchItem(int(episode_rating_key))
        try:
            episode.deletePoster()
        except Exception as e:
            logger.debug(f"Plex deletePoster notice for episode {episode_rating_key}: {e}")
        try:
            episode.unlockPoster()
        except Exception as e:
            logger.debug(f"Plex unlockPoster notice for episode {episode_rating_key}: {e}")
        logger.info(f"✓ Reverted episode card in Plex for {episode.title} (S{episode.seasonNumber:02d}E{episode.episodeNumber:02d})")

    def get_show_seasons(self, show_rating_key: str) -> List[Dict[str, Any]]:
        """Fetch all seasons for a show from Plex."""
        server = self.server
        show = server.fetchItem(int(show_rating_key))
        return [
            {
                "rating_key": str(s.ratingKey),
                "season_number": s.seasonNumber,
                "title": s.title,
                "has_poster": bool(getattr(s, 'thumb', None) or getattr(s, 'thumbUrl', None))
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

    def get_all_movies(self, target_library: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all movies from Plex with TMDb IDs, collection info, and artwork."""
        movie_section = self.get_movie_section(target_library=target_library)
        plex_movies = movie_section.all()

        result = []
        for m in plex_movies:
            tmdb_id = self._extract_tmdb_id(m)
            imdb_id = self._extract_imdb_id(m)
            poster_url = m.posterUrl if hasattr(m, 'posterUrl') else (m.thumbUrl if hasattr(m, 'thumbUrl') else None)
            art_url = m.artUrl if hasattr(m, 'artUrl') else None

            # Collections
            collections = [c.tag for c in getattr(m, 'collections', []) if getattr(c, 'tag', None)]
            coll_name = collections[0] if collections else None

            # Duration in minutes
            duration_mins = round(m.duration / 60000) if getattr(m, 'duration', None) else None

            result.append({
                "rating_key": str(m.ratingKey),
                "title": m.title,
                "year": getattr(m, 'year', None),
                "duration": duration_mins,
                "summary": getattr(m, 'summary', None),
                "tmdb_id": tmdb_id,
                "imdb_id": imdb_id,
                "poster_url": poster_url,
                "backdrop_url": art_url,
                "collection_name": coll_name,
                "collections": collections,
                "library_section_id": str(movie_section.key),
                "library_name": movie_section.title
            })

        return result

    def get_movie_collections(self, target_library: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all collections from the movie library."""
        movie_section = self.get_movie_section(target_library=target_library)
        result = []
        try:
            collections = movie_section.collections()
            for c in collections:
                items = c.items() if hasattr(c, 'items') else []
                poster_url = c.posterUrl if hasattr(c, 'posterUrl') else (c.thumbUrl if hasattr(c, 'thumbUrl') else None)
                tmdb_id = self._extract_tmdb_id(c)

                movie_keys = [str(item.ratingKey) for item in items]
                movie_titles = [item.title for item in items]

                result.append({
                    "rating_key": str(c.ratingKey),
                    "title": c.title,
                    "poster_url": poster_url,
                    "movie_count": len(items),
                    "movie_keys": movie_keys,
                    "movie_titles": movie_titles,
                    "tmdb_collection_id": tmdb_id,
                    "library_section_id": str(movie_section.key),
                    "library_name": movie_section.title
                })
        except Exception as e:
            logger.error(f"Failed to fetch collections from Plex: {e}")
        return result

    def upload_movie_poster(self, movie_rating_key: str, file_path_or_url: str, force_live: bool = False):
        """Upload a poster to a Plex movie (gated by TEST_MODE unless force_live=True)."""
        from backend.config import TEST_MODE
        if TEST_MODE and not force_live:
            logger.info(f"🧪 [TEST MODE] Skipped upload to Plex for movie ID {movie_rating_key}. (Test mode active)")
            return

        server = self.server
        movie = server.fetchItem(int(movie_rating_key))
        if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
            movie.uploadPoster(url=file_path_or_url)
        else:
            movie.uploadPoster(filepath=file_path_or_url)
        logger.info(f"✓ Uploaded poster to Plex for movie '{movie.title}'")

    def revert_movie_poster(self, movie_rating_key: str, force_live: bool = False):
        """Revert a movie poster back to Plex default."""
        from backend.config import TEST_MODE
        if TEST_MODE and not force_live:
            logger.info(f"🧪 [TEST MODE] Skipped reverting movie ID {movie_rating_key} in Plex. (Test mode active)")
            return

        server = self.server
        movie = server.fetchItem(int(movie_rating_key))
        try:
            movie.deletePoster()
        except Exception as e:
            logger.debug(f"Plex deletePoster notice for movie {movie_rating_key}: {e}")
        try:
            movie.unlockPoster()
        except Exception as e:
            logger.debug(f"Plex unlockPoster notice for movie {movie_rating_key}: {e}")
        logger.info(f"✓ Reverted poster in Plex for movie '{movie.title}'")

    def upload_collection_poster(self, collection_rating_key: str, file_path_or_url: str, force_live: bool = False):
        """Upload a poster to a Plex collection (gated by TEST_MODE unless force_live=True)."""
        from backend.config import TEST_MODE
        if TEST_MODE and not force_live:
            logger.info(f"🧪 [TEST MODE] Skipped upload to Plex for collection ID {collection_rating_key}. (Test mode active)")
            return

        server = self.server
        coll = server.fetchItem(int(collection_rating_key))
        if file_path_or_url.startswith("http://") or file_path_or_url.startswith("https://"):
            coll.uploadPoster(url=file_path_or_url)
        else:
            coll.uploadPoster(filepath=file_path_or_url)
        logger.info(f"✓ Uploaded poster to Plex for collection '{coll.title}'")

    def revert_collection_poster(self, collection_rating_key: str, force_live: bool = False):
        """Revert a collection poster back to Plex default."""
        from backend.config import TEST_MODE
        if TEST_MODE and not force_live:
            logger.info(f"🧪 [TEST MODE] Skipped reverting collection ID {collection_rating_key} in Plex. (Test mode active)")
            return

        server = self.server
        coll = server.fetchItem(int(collection_rating_key))
        try:
            coll.deletePoster()
        except Exception as e:
            logger.debug(f"Plex deletePoster notice for collection {collection_rating_key}: {e}")
        try:
            coll.unlockPoster()
        except Exception as e:
            logger.debug(f"Plex unlockPoster notice for collection {collection_rating_key}: {e}")
        logger.info(f"✓ Reverted poster in Plex for collection '{coll.title}'")


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

    def _extract_tvdb_id(self, item) -> Optional[int]:
        """Extract TheTVDB ID from Plex GUIDs (e.g., 'tvdb://80348' or 'thetvdb://80348')."""
        if hasattr(item, 'guids'):
            for g in item.guids:
                if g.id.startswith('tvdb://'):
                    try:
                        return int(g.id.replace('tvdb://', ''))
                    except ValueError:
                        pass
                elif 'thetvdb://' in g.id:
                    match = re.search(r'thetvdb://(\d+)', g.id)
                    if match:
                        return int(match.group(1))
                        
        # Fallback check item.guid
        if hasattr(item, 'guid'):
            match = re.search(r'(?:tvdb|thetvdb)://(\d+)', item.guid)
            if match:
                return int(match.group(1))
        return None

    def _extract_imdb_id(self, item) -> Optional[str]:
        """Extract IMDb ID from Plex GUIDs (e.g., 'imdb://tt0078748')."""
        if hasattr(item, 'guids'):
            for g in item.guids:
                if g.id.startswith('imdb://'):
                    return g.id.replace('imdb://', '')
        if hasattr(item, 'guid'):
            match = re.search(r'imdb://(tt\d+)', item.guid)
            if match:
                return match.group(1)
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

