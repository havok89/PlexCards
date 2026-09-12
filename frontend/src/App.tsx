import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Show, Movie, MovieCollection, AppConfig, AuthStatus, AuthUser, PlexLibrary } from './types';
import { api } from './api';
import { Navbar } from './components/Navbar';
import { FilterBar } from './components/FilterBar';
import { ShowCard } from './components/ShowCard';
import { MovieCard } from './components/MovieCard';
import { CollectionCard } from './components/CollectionCard';
import { ShowStudioModal } from './components/ShowStudioModal';
import { MovieStudioModal } from './components/MovieStudioModal';
import { CollectionStudioModal } from './components/CollectionStudioModal';
import { SettingsModal } from './components/SettingsModal';
import { LoginPage } from './components/LoginPage';
import { useToast } from './context/ToastContext';
import { Tv, Film, Layers, Loader2, ArrowUpDown, Filter, Sparkles, CheckCircle2 } from 'lucide-react';

export const App: React.FC = () => {
  const [mediaType, setMediaType] = useState<'shows' | 'movies'>('shows');
  const [shows, setShows] = useState<Show[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [collections, setCollections] = useState<MovieCollection[]>([]);
  const [libraries, setLibraries] = useState<PlexLibrary[]>([]);
  const [activeLibrary, setActiveLibrary] = useState<string>('all');
  const [activeTvLibrary, setActiveTvLibrary] = useState<string>('all');
  const [activeMovieLibrary, setActiveMovieLibrary] = useState<string>('all');

  const [config, setConfig] = useState<AppConfig>({
    test_mode: true,
    tv_library: 'TV shows',
    poll_interval_hours: 12
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [checkingAuth, setCheckingAuth] = useState<boolean>(true);
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterMode, setFilterMode] = useState<string>('all');

  // Movie mode states
  const [movieSubView, setMovieSubView] = useState<'movies' | 'collections'>('movies');
  const [movieSort, setMovieSort] = useState<string>('title_asc');
  const [movieFilter, setMovieFilter] = useState<'all' | 'custom' | 'default'>('all');

  // Modals
  const [selectedShow, setSelectedShow] = useState<Show | null>(null);
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);
  const [selectedCollection, setSelectedCollection] = useState<MovieCollection | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  const { showToast } = useToast();

  const loadData = useCallback(async (targetLib?: string) => {
    try {
      const [conf, libRes] = await Promise.all([
        api.getConfig(),
        api.getLibraries().catch(() => ({
          libraries: [],
          active_library: 'all',
          active_tv_library: 'all',
          active_movie_library: 'all'
        }))
      ]);
      setConfig(conf);
      setLibraries(libRes.libraries || []);
      
      const tvLib = libRes.active_tv_library || libRes.active_library || 'all';
      const movieLib = libRes.active_movie_library || 'all';
      setActiveTvLibrary(tvLib);
      setActiveMovieLibrary(movieLib);

      const libToUse = targetLib !== undefined ? targetLib : tvLib;
      setActiveLibrary(libToUse);

      const [showsList, moviesList, collsList] = await Promise.all([
        api.getShows(libToUse === 'all' ? undefined : libToUse).catch(() => []),
        api.getMovies(movieLib === 'all' ? undefined : movieLib, undefined, movieSort).catch(() => []),
        api.getCollections(movieLib === 'all' ? undefined : movieLib).catch(() => [])
      ]);
      setShows(showsList);
      setMovies(moviesList);
      setCollections(collsList);
    } catch (e) {
      console.error('Failed to load data:', e);
    } finally {
      setLoading(false);
    }
  }, [movieSort]);

  const loadMovieData = useCallback(async (targetLib?: string, sort: string = movieSort) => {
    setLoading(true);
    try {
      const libToUse = targetLib !== undefined ? targetLib : activeMovieLibrary;
      const [moviesList, collsList] = await Promise.all([
        api.getMovies(libToUse === 'all' ? undefined : libToUse, undefined, sort),
        api.getCollections(libToUse === 'all' ? undefined : libToUse)
      ]);
      setMovies(moviesList);
      setCollections(collsList);
    } catch (e) {
      console.error('Failed to load movie data:', e);
    } finally {
      setLoading(false);
    }
  }, [activeMovieLibrary, movieSort]);

  const checkAuthAndInit = useCallback(async () => {
    try {
      const status = await api.getAuthStatus();
      setAuthStatus(status);
      if (!status.auth_enabled || status.authenticated) {
        await loadData();
      }
    } catch (e) {
      console.error('Auth check failed:', e);
      await loadData();
    } finally {
      setCheckingAuth(false);
    }
  }, [loadData]);

  useEffect(() => {
    checkAuthAndInit();
  }, [checkAuthAndInit]);

  const handleLoginSuccess = (user: AuthUser) => {
    setAuthStatus({ auth_enabled: true, authenticated: true, user });
    loadData();
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (e) {
      console.error('Logout error:', e);
    }
    setAuthStatus({ auth_enabled: true, authenticated: false, user: null });
    setShows([]);
    setMovies([]);
  };

  // Toggle between TV Shows and Movies
  const handleMediaTypeChange = (newType: 'shows' | 'movies') => {
    setMediaType(newType);
    setSearchQuery('');
    if (newType === 'movies') {
      setActiveLibrary(activeMovieLibrary);
      loadMovieData(activeMovieLibrary);
    } else {
      setActiveLibrary(activeTvLibrary);
      loadData(activeTvLibrary);
    }
  };

  const handleSelectLibrary = async (key: string) => {
    setActiveLibrary(key);
    setLoading(true);
    try {
      if (mediaType === 'movies') {
        setActiveMovieLibrary(key);
        if (key !== 'all') {
          await api.switchLibrary(key, 'movie');
        }
        await loadMovieData(key);
      } else {
        setActiveTvLibrary(key);
        if (key !== 'all') {
          await api.switchLibrary(key, 'show');
        }
        const showsList = await api.getShows(key === 'all' ? undefined : key);
        setShows(showsList);
      }
    } catch (e) {
      console.error('Failed to switch library:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleScan = async () => {
    const typeLabel = mediaType === 'shows' ? 'TV shows' : 'movies';
    const libName = activeLibrary === 'all'
      ? `all ${typeLabel} libraries`
      : (libraries.find((l) => l.key === activeLibrary)?.title || 'selected library');

    if (!window.confirm(`Are you sure you want to scan ${libName}? This will query your Plex server and sync media records.`)) {
      return;
    }

    setIsScanning(true);
    try {
      if (mediaType === 'movies') {
        const res = await api.scanLibrary(activeLibrary === 'all' ? undefined : activeLibrary, 'movie');
        showToast({
          type: 'success',
          title: 'Movie Scan Complete',
          message: `Indexed ${res.total_movies || 0} movies and ${res.total_collections || 0} collections from Plex.`
        });
        await loadMovieData(activeLibrary);
      } else {
        const res = await api.scanLibrary(activeLibrary === 'all' ? undefined : activeLibrary, 'show');
        showToast({
          type: 'success',
          title: 'TV Scan Complete',
          message: `Indexed ${res.indexed_shows || 0} TV shows from Plex.`
        });
        await loadData(activeLibrary);
      }
    } catch (e) {
      showToast({
        type: 'error',
        title: 'Scan Failed',
        message: String(e)
      });
    } finally {
      setIsScanning(false);
    }
  };

  const isShowContinuing = (status?: string): boolean => {
    if (!status) return true;
    const s = status.trim().toLowerCase();
    return s !== 'ended' && s !== 'canceled' && s !== 'cancelled';
  };

  const continuingCount = useMemo(() => {
    return shows.filter((s) => isShowContinuing(s.status)).length;
  }, [shows]);

  const filteredShows = useMemo(() => {
    return shows.filter((s) => {
      const matchesSearch = s.title.toLowerCase().includes(searchQuery.toLowerCase());
      let matchesFilter = true;
      if (filterMode === 'continuing') {
        matchesFilter = isShowContinuing(s.status);
      } else if (filterMode !== 'all') {
        matchesFilter = s.mode === filterMode;
      }
      return matchesSearch && matchesFilter;
    });
  }, [shows, searchQuery, filterMode]);

  // Movies filtering & counts
  const customPostersCount = useMemo(() => {
    return movies.filter((m) => m.has_custom_poster === 1).length;
  }, [movies]);

  const defaultPostersCount = useMemo(() => {
    return movies.filter((m) => !m.has_custom_poster || m.has_custom_poster === 0).length;
  }, [movies]);

  const filteredMovies = useMemo(() => {
    return movies.filter((m) => {
      const matchesSearch = m.title.toLowerCase().includes(searchQuery.toLowerCase());
      let matchesFilter = true;
      if (movieFilter === 'custom') {
        matchesFilter = m.has_custom_poster === 1;
      } else if (movieFilter === 'default') {
        matchesFilter = !m.has_custom_poster || m.has_custom_poster === 0;
      }
      return matchesSearch && matchesFilter;
    });
  }, [movies, searchQuery, movieFilter]);

  const filteredCollections = useMemo(() => {
    return collections.filter((c) =>
      c.title.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [collections, searchQuery]);

  // Infinite scroll / chunked rendering state to avoid flooding the DOM and Plex with 400+ simultaneous requests
  const [visibleLimit, setVisibleLimit] = useState<number>(48);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    setVisibleLimit(48);
  }, [mediaType, movieSubView, searchQuery, filterMode, movieFilter, activeLibrary]);

  useEffect(() => {
    if (!loadMoreRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisibleLimit((prev) => prev + 36);
        }
      },
      { rootMargin: '400px' }
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [mediaType, movieSubView, filteredShows.length, filteredMovies.length, filteredCollections.length]);

  const displayedShows = useMemo(() => filteredShows.slice(0, visibleLimit), [filteredShows, visibleLimit]);
  const displayedMovies = useMemo(() => filteredMovies.slice(0, visibleLimit), [filteredMovies, visibleLimit]);
  const displayedCollections = useMemo(() => filteredCollections.slice(0, visibleLimit), [filteredCollections, visibleLimit]);

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-dark-950 flex flex-col items-center justify-center text-gray-400 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
        <p className="text-sm">Loading PlexCards...</p>
      </div>
    );
  }

  if (authStatus?.auth_enabled && !authStatus?.authenticated) {
    return <LoginPage onSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-dark-950 text-gray-200 overflow-x-hidden">
      <Navbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onScan={handleScan}
        isScanning={isScanning}
        onOpenSettings={() => setIsSettingsOpen(true)}
        listenerConnected={config.listener_connected}
        currentUser={authStatus?.user}
        onLogout={authStatus?.auth_enabled ? handleLogout : undefined}
        libraries={libraries}
        activeLibrary={activeLibrary}
        onSelectLibrary={handleSelectLibrary}
        mediaType={mediaType}
        onMediaTypeChange={handleMediaTypeChange}
      />

      {mediaType === 'shows' ? (
        <FilterBar
          filterMode={filterMode}
          onFilterChange={setFilterMode}
          totalCount={shows.length}
          continuingCount={continuingCount}
          testMode={config.test_mode}
          tvLibrary={config.tv_library}
        />
      ) : (
        /* Movie Mode Secondary Bar */
        <div className="bg-dark-900 border-b border-gray-800 px-3 sm:px-6 py-2.5">
          <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
            {/* View Sub-Tabs: Movies | Collections */}
            <div className="flex items-center gap-1 bg-dark-950 p-1 rounded-xl border border-gray-800">
              <button
                onClick={() => setMovieSubView('movies')}
                className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-lg text-xs font-semibold transition ${
                  movieSubView === 'movies'
                    ? 'bg-brand-500 text-dark-950 shadow-md shadow-brand-500/20'
                    : 'text-gray-400 hover:text-white hover:bg-dark-850'
                }`}
              >
                <Film className="w-3.5 h-3.5" />
                <span><span className="sm:hidden">Movies</span><span className="hidden sm:inline">All Movies</span> ({movies.length})</span>
              </button>
              <button
                onClick={() => setMovieSubView('collections')}
                className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-lg text-xs font-semibold transition ${
                  movieSubView === 'collections'
                    ? 'bg-brand-500 text-dark-950 shadow-md shadow-brand-500/20'
                    : 'text-gray-400 hover:text-white hover:bg-dark-850'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span><span className="sm:hidden">Collections</span><span className="hidden sm:inline">Franchise Collections</span> ({collections.length})</span>
              </button>
            </div>

            {/* Movie Filters & Sorter (when viewing movies) */}
            {movieSubView === 'movies' && (
              <div className="flex flex-wrap items-center gap-2">
                {/* Filter Pills */}
                <div className="flex items-center gap-1 bg-dark-950 p-1 rounded-xl border border-gray-800 text-xs">
                  <button
                    onClick={() => setMovieFilter('all')}
                    className={`px-2.5 py-1 rounded-lg font-medium transition ${
                      movieFilter === 'all'
                        ? 'bg-dark-800 text-white shadow-sm'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    All ({movies.length})
                  </button>
                  <button
                    onClick={() => setMovieFilter('custom')}
                    className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1 ${
                      movieFilter === 'custom'
                        ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-500/40'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    Custom ({customPostersCount})
                  </button>
                  <button
                    onClick={() => setMovieFilter('default')}
                    className={`px-2.5 py-1 rounded-lg font-medium transition ${
                      movieFilter === 'default'
                        ? 'bg-dark-800 text-white shadow-sm'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    Default ({defaultPostersCount})
                  </button>
                </div>

                {/* Sort Dropdown */}
                <div className="flex items-center gap-1 bg-dark-950 border border-gray-800 rounded-xl px-2.5 py-1.5 text-xs text-gray-300">
                  <ArrowUpDown className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                  <select
                    value={movieSort}
                    onChange={(e) => {
                      const newSort = e.target.value;
                      setMovieSort(newSort);
                      loadMovieData(activeLibrary, newSort);
                    }}
                    className="bg-transparent text-xs text-white focus:outline-none cursor-pointer pr-1 font-medium"
                  >
                    <option value="title_asc" className="bg-dark-900 text-white">Title (A–Z)</option>
                    <option value="title_desc" className="bg-dark-900 text-white">Title (Z–A)</option>
                    <option value="year_desc" className="bg-dark-900 text-white">Release Year (Newest)</option>
                    <option value="year_asc" className="bg-dark-900 text-white">Release Year (Oldest)</option>
                    <option value="recently_added" className="bg-dark-900 text-white">Recently Added</option>
                  </select>
                </div>
              </div>
            )}

            {/* Test Mode Badge */}
            {config.test_mode && (
              <div className="hidden sm:flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-950/50 border border-amber-500/30 text-amber-300 text-[11px] font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                TEST MODE
              </div>
            )}
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-6">
        {loading ? (
          <div className="text-center py-24 text-gray-500 flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
            <p>Loading your Plex {mediaType === 'shows' ? 'TV' : 'Movie'} library...</p>
          </div>
        ) : mediaType === 'shows' ? (
          /* TV Shows View */
          filteredShows.length === 0 ? (
            <div className="text-center py-20 bg-dark-900 border border-gray-800 rounded-xl max-w-md mx-auto p-8">
              <Tv className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white">No shows found</h3>
              <p className="text-sm text-gray-400 mt-1 mb-4">
                {shows.length === 0
                  ? 'Scan your Plex TV library to index your TV shows.'
                  : 'No shows match your current search or filter.'}
              </p>
              {shows.length === 0 && (
                <button
                  onClick={handleScan}
                  className="bg-brand-500 text-dark-950 font-bold px-4 py-2 rounded-lg text-sm transition hover:bg-brand-600"
                >
                  Scan Plex TV Now
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 sm:gap-5">
              {displayedShows.map((show) => (
                <ShowCard
                  key={show.rating_key}
                  show={show}
                  onClick={() => setSelectedShow(show)}
                />
              ))}
              {filteredShows.length > visibleLimit && (
                <div ref={loadMoreRef} className="col-span-full py-8 flex items-center justify-center text-xs text-gray-500 gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
                  <span>Loading more shows... ({displayedShows.length} of {filteredShows.length})</span>
                </div>
              )}
            </div>
          )
        ) : (
          /* Movie Mode View */
          movieSubView === 'movies' ? (
            filteredMovies.length === 0 ? (
              <div className="text-center py-20 bg-dark-900 border border-gray-800 rounded-xl max-w-md mx-auto p-8">
                <Film className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-white">No movies found</h3>
                <p className="text-sm text-gray-400 mt-1 mb-4">
                  {movies.length === 0
                    ? 'Scan your Plex Movie library to index your films.'
                    : 'No movies match your current search or filter.'}
                </p>
                {movies.length === 0 && (
                  <button
                    onClick={handleScan}
                    className="bg-brand-500 text-dark-950 font-bold px-4 py-2 rounded-lg text-sm transition hover:bg-brand-600"
                  >
                    Scan Plex Movies Now
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 sm:gap-5">
                {displayedMovies.map((movie) => (
                  <MovieCard
                    key={movie.rating_key}
                    movie={movie}
                    onClick={() => setSelectedMovie(movie)}
                  />
                ))}
                {filteredMovies.length > visibleLimit && (
                  <div ref={loadMoreRef} className="col-span-full py-8 flex items-center justify-center text-xs text-gray-500 gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
                    <span>Loading more movies... ({displayedMovies.length} of {filteredMovies.length})</span>
                  </div>
                )}
              </div>
            )
          ) : (
            /* Movie Collections View */
            filteredCollections.length === 0 ? (
              <div className="text-center py-20 bg-dark-900 border border-gray-800 rounded-xl max-w-md mx-auto p-8">
                <Layers className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-white">No collections found</h3>
                <p className="text-sm text-gray-400 mt-1 mb-4">
                  {collections.length === 0
                    ? 'Ensure Plex has automatic collections turned on or scan your movie library.'
                    : 'No collections match your search.'}
                </p>
                {collections.length === 0 && (
                  <button
                    onClick={handleScan}
                    className="bg-brand-500 text-dark-950 font-bold px-4 py-2 rounded-lg text-sm transition hover:bg-brand-600"
                  >
                    Scan Plex Movies Now
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 sm:gap-5">
                {displayedCollections.map((coll) => (
                  <CollectionCard
                    key={coll.rating_key}
                    collection={coll}
                    onClick={() => setSelectedCollection(coll)}
                  />
                ))}
                {filteredCollections.length > visibleLimit && (
                  <div ref={loadMoreRef} className="col-span-full py-8 flex items-center justify-center text-xs text-gray-500 gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
                    <span>Loading more collections... ({displayedCollections.length} of {filteredCollections.length})</span>
                  </div>
                )}
              </div>
            )
          )
        )}
      </main>

      {/* Modals */}
      {selectedShow && (
        <ShowStudioModal
          show={selectedShow}
          testMode={config.test_mode}
          hasGeminiKey={config.has_gemini_key}
          onClose={() => setSelectedShow(null)}
          onShowUpdated={loadData}
        />
      )}

      {selectedMovie && (
        <MovieStudioModal
          movie={selectedMovie}
          testMode={config.test_mode}
          onClose={() => setSelectedMovie(null)}
          onUpdated={() => loadMovieData(activeLibrary)}
        />
      )}

      {selectedCollection && (
        <CollectionStudioModal
          collection={selectedCollection}
          testMode={config.test_mode}
          onClose={() => setSelectedCollection(null)}
          onUpdated={() => loadMovieData(activeLibrary)}
        />
      )}

      {isSettingsOpen && (
        <SettingsModal
          onClose={() => setIsSettingsOpen(false)}
          onShowsUpdated={loadData}
          testMode={config.test_mode}
          tvLibrary={config.tv_library}
          listenerConnected={config.listener_connected}
          hasGeminiKey={config.has_gemini_key}
          hasTvdbKey={config.has_tvdb_key}
          hasTmdbKey={config.has_tmdb_key}
        />
      )}
    </div>
  );
};
