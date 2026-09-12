import React, { useState, useEffect, useMemo } from 'react';
import { MovieCollection, Movie, MediuxFranchiseSet, TmdbPosterOption } from '../types';
import { api } from '../api';
import {
  X, Check, RefreshCw, Layers, ExternalLink, Image as ImageIcon,
  Sparkles, Film, AlertCircle, ZoomIn
} from 'lucide-react';
import { useToast } from '../context/ToastContext';

interface CollectionStudioModalProps {
  collection: MovieCollection;
  onClose: () => void;
  onUpdated: () => void;
  testMode?: boolean;
}

// Normalizes movie or poster titles for fuzzy matching
const normalize = (str: string) => {
  return str
    .toLowerCase()
    .replace(/\(\d{4}\)/g, '')
    .replace(/\b(part|vol|volume|chapter)\s*(1|i)\b/g, 'part1')
    .replace(/\b(part|vol|volume|chapter)\s*(2|ii)\b/g, 'part2')
    .replace(/\b(part|vol|volume|chapter)\s*(3|iii)\b/g, 'part3')
    .replace(/\b(part|vol|volume|chapter)\s*(4|iv)\b/g, 'part4')
    .replace(/\b(part|vol|volume|chapter)\s*(5|v)\b/g, 'part5')
    .replace(/[^a-z0-9]/g, '');
};

const extractYear = (str: string) => {
  const m = str.match(/\b(19\d\d|20\d\d)\b/);
  return m ? parseInt(m[1], 10) : null;
};

const getTitleParts = (str: string) => {
  const clean = str.replace(/\(\d{4}\)/g, '').trim();
  const parts = clean.split(/[:\-–—]/).map((s) => s.trim()).filter(Boolean);
  return {
    full: normalize(clean),
    main: normalize(parts[0] || clean),
    subtitles: parts.slice(1).map(normalize)
  };
};

function scoreMatch(movie: Movie, poster: { id: string; title: string; url: string }) {
  const mParts = getTitleParts(movie.title);
  const pParts = getTitleParts(poster.title);
  const pYear = extractYear(poster.title);

  let score = 0;

  // 1. Exact full title match
  if (mParts.full === pParts.full) {
    score += 10000;
  }

  // 2. Year check
  if (movie.year && pYear) {
    if (movie.year === pYear) {
      score += 2500;
    } else {
      score -= 4000; // Strong penalty for mismatching release years
    }
  }

  // 3. Subtitle check (e.g. 'The Bone Temple' vs '28 Years Later')
  if (mParts.subtitles.length > 0) {
    const matchedSub = mParts.subtitles.some(
      (sub) =>
        pParts.full.includes(sub) ||
        pParts.subtitles.some((ps) => ps.includes(sub) || sub.includes(ps)) ||
        sub.includes(pParts.full)
    );
    if (matchedSub) {
      score += 3000;
    } else {
      score -= 2000; // Movie has subtitle but poster doesn't have it
    }
  } else {
    if (pParts.subtitles.length > 0) {
      score -= 2000; // Poster has subtitle but movie doesn't
    }
  }

  // 4. Main title similarity
  if (mParts.main === pParts.main) {
    score += 1000;
  } else if (mParts.main.includes(pParts.main) || pParts.main.includes(mParts.main)) {
    score += 200;
  }

  // 5. Substring length ratio penalty/bonus (prevents short prefix hijacking)
  if (mParts.full.includes(pParts.full) || pParts.full.includes(mParts.full)) {
    const ratio = Math.min(mParts.full.length, pParts.full.length) / Math.max(mParts.full.length, pParts.full.length);
    score += Math.round(ratio * 500);
  }

  return score;
}

function matchMoviesToSetPosters(
  movies: Movie[],
  posters: { id: string; title: string; url: string }[]
): Map<string, { id: string; title: string; url: string }> {
  const assignments = new Map<string, { id: string; title: string; url: string }>();
  if (!posters || posters.length === 0) return assignments;

  const candidates: {
    movie: Movie;
    poster: { id: string; title: string; url: string };
    score: number;
  }[] = [];

  for (const movie of movies) {
    for (const poster of posters) {
      const score = scoreMatch(movie, poster);
      candidates.push({ movie, poster, score });
    }
  }

  candidates.sort((a, b) => b.score - a.score);

  const assignedMovies = new Set<string>();
  const assignedPosters = new Set<string>();

  // Pass 1: Assign high confidence positive matches
  for (const { movie, poster, score } of candidates) {
    if (score <= 0) break;
    if (!assignedMovies.has(movie.rating_key) && !assignedPosters.has(poster.id)) {
      assignedMovies.add(movie.rating_key);
      assignedPosters.add(poster.id);
      assignments.set(movie.rating_key, poster);
    }
  }

  // Pass 2: If any movie remains unassigned, attempt fallback to unassigned posters with score > -2000
  for (const movie of movies) {
    if (!assignedMovies.has(movie.rating_key)) {
      const remainingCandidates = candidates.filter(
        (c) => c.movie.rating_key === movie.rating_key && !assignedPosters.has(c.poster.id) && c.score > -2000
      );
      if (remainingCandidates.length > 0) {
        const best = remainingCandidates[0];
        assignedMovies.add(movie.rating_key);
        assignedPosters.add(best.poster.id);
        assignments.set(movie.rating_key, best.poster);
      }
    }
  }

  return assignments;
}

export const CollectionStudioModal: React.FC<CollectionStudioModalProps> = ({ collection, onClose, onUpdated, testMode = false }) => {
  const { showToast } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [isApplying, setIsApplying] = useState(false);
  const [isForceLive, setIsForceLive] = useState(false);

  const [movies, setMovies] = useState<Movie[]>([]);
  const [mediuxSets, setMediuxSets] = useState<MediuxFranchiseSet[]>([]);
  const [tmdbPosters, setTmdbPosters] = useState<TmdbPosterOption[]>([]);

  const [currentBoxsetPoster, setCurrentBoxsetPoster] = useState<string | undefined>(collection.poster_url);
  const [selectedSet, setSelectedSet] = useState<MediuxFranchiseSet | null>(null);
  const [selectedBoxsetOnlyUrl, setSelectedBoxsetOnlyUrl] = useState<string | null>(null);
  const [customOverrides, setCustomOverrides] = useState<Record<string, { id: string; title: string; url: string }>>({});
  const [previewPoster, setPreviewPoster] = useState<{ url: string; title: string; subtitle?: string } | null>(null);

  // Close preview lightbox on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && previewPoster) {
        setPreviewPoster(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [previewPoster]);

  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      setIsLoading(true);
      try {
        const data = await api.getCollectionPosters(collection.rating_key);
        if (isMounted) {
          setMovies(data.movies || []);
          setTmdbPosters(data.tmdb_posters || []);

          let sets = [...(data.mediux_sets || [])];
          if (sets.length > 0) {
            const appliedId = data.applied_mediux_set_id || collection.applied_mediux_set_id;
            let appliedIndex = -1;

            if (appliedId) {
              appliedIndex = sets.findIndex((s) => String(s.id) === String(appliedId));
            }

            // Only surface and select a set if the user previously selected/applied one!
            if (appliedIndex !== -1) {
              if (appliedIndex > 0) {
                const [appliedSet] = sets.splice(appliedIndex, 1);
                sets.unshift(appliedSet);
              }
              setSelectedSet(sets[0]);
            } else {
              setSelectedSet(null);
            }

            setMediuxSets(sets);
          } else {
            setMediuxSets([]);
            setSelectedSet(null);
          }
        }
      } catch (err) {
        console.error('Failed to load collection posters:', err);
        showToast({ type: 'error', message: 'Failed to load franchise sets' });
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    loadData();
    return () => { isMounted = false; };
  }, [collection.rating_key, collection.applied_mediux_set_id]);

  // Reset custom overrides whenever selected set changes
  useEffect(() => {
    setCustomOverrides({});
  }, [selectedSet?.id]);

  // 1-to-1 smart matching between movies in this collection and posters in the selected set
  const autoMatches = useMemo(() => {
    return matchMoviesToSetPosters(movies, selectedSet?.movie_posters || []);
  }, [movies, selectedSet]);

  const getMatchedPoster = (movie: Movie) => {
    return customOverrides[movie.rating_key] || autoMatches.get(movie.rating_key);
  };

  const handleApplyEntireSet = async () => {
    if (!selectedSet) return;
    setIsApplying(true);
    try {
      const moviePosterPayload: { movie_rating_key: string; poster_url: string }[] = [];

      for (const m of movies) {
        const matched = getMatchedPoster(m);
        if (matched) {
          moviePosterPayload.push({
            movie_rating_key: m.rating_key,
            poster_url: matched.url
          });
        }
      }

      const res = await api.applyCollectionSet(
        collection.rating_key,
        selectedSet.collection_poster_url,
        moviePosterPayload,
        selectedSet.id,
        isForceLive
      );

      if (res.test_mode) {
        showToast({
          type: 'info',
          message: `🧪 Test Mode: Simulated applying franchise set across ${res.applied_count} items (saved to cache/test_output/). Check "Live Upload" to push to Plex.`
        });
      } else {
        showToast({ type: 'success', message: `Applied franchise artwork across ${res.applied_count} items!` });
        setCurrentBoxsetPoster(selectedSet.collection_poster_url);
        collection.applied_mediux_set_id = selectedSet.id;
        onUpdated();
      }
    } catch (err: any) {
      showToast({ type: 'error', message: err.message || 'Failed to apply franchise set' });
    } finally {
      setIsApplying(false);
    }
  };

  const handleApplyBoxsetOnly = async (url: string) => {
    setIsApplying(true);
    try {
      const res = await api.applyCollectionSet(collection.rating_key, url, [], undefined, isForceLive);
      if (res.test_mode) {
        showToast({
          type: 'info',
          message: '🧪 Test Mode: Simulated boxset cover upload (saved to cache/test_output/). Check "Live Upload" to push to Plex.'
        });
      } else {
        showToast({ type: 'success', message: 'Collection boxset poster applied to Plex!' });
        setCurrentBoxsetPoster(url);
        setSelectedBoxsetOnlyUrl(null);
        onUpdated();
      }
    } catch (err: any) {
      showToast({ type: 'error', message: err.message || 'Failed to apply boxset poster' });
    } finally {
      setIsApplying(false);
    }
  };

  const activeBoxsetPreview = selectedBoxsetOnlyUrl || selectedSet?.collection_poster_url || currentBoxsetPoster;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-2 sm:p-4 overflow-y-auto">
      <div className="bg-dark-900 border border-gray-800 rounded-2xl w-full max-w-6xl max-h-[94vh] flex flex-col shadow-2xl overflow-hidden animate-fadeIn">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-gray-800 flex items-center justify-between gap-4 bg-dark-950/60">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-brand-500/10 border border-brand-500/30 text-brand-400">
                <Layers className="w-4 h-4" />
              </div>
              <h2 className="text-lg sm:text-xl font-bold text-white truncate" title={collection.title}>
                {collection.title}
              </h2>
              <span className="text-xs bg-dark-800 border border-gray-700 text-gray-300 px-2 py-0.5 rounded-full font-medium">
                {collection.movie_count} {collection.movie_count === 1 ? 'Movie' : 'Movies'}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Apply unified artwork for the collection boxset and all included movies.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {testMode && (
              <label className="flex items-center gap-1.5 text-xs text-amber-400 cursor-pointer bg-amber-500/10 border border-amber-500/30 px-2.5 py-1 rounded-lg hover:bg-amber-500/15 transition select-none">
                <input
                  type="checkbox"
                  checked={isForceLive}
                  onChange={(e) => setIsForceLive(e.target.checked)}
                  className="accent-amber-500 rounded"
                />
                <span>Live Upload</span>
              </label>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-dark-800 transition shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Left Column: Boxset Cover & Batch Action */}
          <div className="md:col-span-4 flex flex-col items-center gap-4">
            <div className="w-full max-w-[280px]">
              <div
                className={`relative aspect-[2/3] rounded-xl overflow-hidden border-2 border-brand-500/40 bg-dark-950 shadow-xl group ${
                  activeBoxsetPreview ? 'cursor-zoom-in' : ''
                }`}
                onClick={() =>
                  activeBoxsetPreview &&
                  setPreviewPoster({
                    url: activeBoxsetPreview,
                    title: `${collection.title} (Boxset Cover)`,
                    subtitle: selectedSet ? `${selectedSet.set_name} • by ${selectedSet.creator}` : undefined
                  })
                }
                title={activeBoxsetPreview ? 'Click to preview larger' : undefined}
              >
                {activeBoxsetPreview ? (
                  <>
                    <img
                      src={activeBoxsetPreview}
                      alt={collection.title}
                      className="w-full h-full object-cover transition duration-300 group-hover:scale-105"
                    />
                    <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                      <div className="p-2 rounded-full bg-black/60 text-white backdrop-blur-sm shadow">
                        <ZoomIn className="w-5 h-5" />
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-gray-500">
                    <Layers className="w-12 h-12 mb-2 text-brand-500/50" />
                    <span className="text-xs">No boxset cover</span>
                  </div>
                )}

                <div className="absolute top-2 left-2 bg-black/75 backdrop-blur-md text-brand-400 border border-brand-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
                  <Layers className="w-3 h-3" /> Boxset Poster
                </div>
              </div>

              {/* Action Button */}
              <div className="mt-4 flex flex-col gap-2">
                {selectedSet ? (
                  <button
                    onClick={handleApplyEntireSet}
                    disabled={isApplying}
                    className="w-full py-2.5 px-4 bg-brand-500 hover:bg-brand-400 disabled:opacity-40 text-dark-950 font-bold rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20 transition"
                  >
                    {isApplying ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                    {isApplying ? 'Applying Franchise Set...' : 'Apply Entire Franchise Set'}
                  </button>
                ) : (
                  <div className="text-center py-2.5 px-3 rounded-xl bg-dark-950/40 border border-gray-800 text-xs text-gray-500 font-medium">
                    Select a franchise set to preview & apply artwork
                  </div>
                )}

                {selectedBoxsetOnlyUrl && (
                  <button
                    onClick={() => handleApplyBoxsetOnly(selectedBoxsetOnlyUrl)}
                    disabled={isApplying}
                    className="w-full py-2 px-3 bg-dark-800 hover:bg-dark-750 text-brand-400 border border-brand-500/30 font-semibold rounded-xl text-xs flex items-center justify-center gap-1.5 transition"
                  >
                    <Check className="w-3.5 h-3.5" /> Apply Boxset Cover Only
                  </button>
                )}
              </div>

              {/* Movies in this collection */}
              <div className="mt-4 p-3 rounded-xl bg-dark-950/60 border border-gray-800/80">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-xs text-gray-300">
                    Movies in this Collection ({movies.length})
                  </span>
                  {selectedSet ? (
                    <span className="text-[10px] text-brand-400 font-medium">
                      {movies.filter((m) => !!getMatchedPoster(m)).length}/{movies.length} matched
                    </span>
                  ) : (
                    <span className="text-[10px] text-gray-500">No set selected</span>
                  )}
                </div>
                <div className="flex flex-col gap-2 max-h-60 overflow-y-auto pr-1">
                  {movies.map((m) => {
                    const matched = getMatchedPoster(m);
                    return (
                      <div
                        key={m.rating_key}
                        className="flex items-center justify-between gap-2 p-1.5 rounded-lg bg-dark-900/60 border border-gray-800/50 text-xs"
                      >
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          <Film className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                          <div className="truncate">
                            <span className="text-gray-200 font-medium truncate block" title={m.title}>
                              {m.title}
                            </span>
                            {m.year && <span className="text-gray-500 text-[10px]">({m.year})</span>}
                          </div>
                        </div>

                        {selectedSet && selectedSet.movie_posters.length > 0 ? (
                          <div className="flex items-center gap-2 shrink-0">
                            {matched ? (
                              <div
                                onClick={() =>
                                  setPreviewPoster({
                                    url: matched.url,
                                    title: `${m.title}${m.year ? ` (${m.year})` : ''}`,
                                    subtitle: `Matched poster from ${selectedSet.set_name}`
                                  })
                                }
                                className="relative cursor-zoom-in group/mthumb"
                                title="Click to preview larger"
                              >
                                <img
                                  src={matched.url}
                                  alt={m.title}
                                  className="w-6 h-9 object-cover rounded shadow border border-brand-500/40 group-hover/mthumb:border-brand-400 transition"
                                />
                                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/mthumb:opacity-100 transition-opacity rounded flex items-center justify-center">
                                  <ZoomIn className="w-3 h-3 text-white" />
                                </div>
                              </div>
                            ) : (
                              <div className="w-6 h-9 rounded border border-dashed border-gray-700 flex items-center justify-center text-gray-600 text-[9px]">
                                ?
                              </div>
                            )}

                            <select
                              value={matched?.id || ''}
                              onChange={(e) => {
                                const chosen = selectedSet.movie_posters.find((p) => p.id === e.target.value);
                                if (chosen) {
                                  setCustomOverrides((prev) => ({ ...prev, [m.rating_key]: chosen }));
                                }
                              }}
                              className="text-[10px] bg-dark-950 border border-gray-750 text-gray-300 rounded px-1.5 py-1 focus:outline-none focus:border-brand-500 max-w-[125px] truncate"
                              title={matched?.title || 'Assign poster'}
                            >
                              {!matched && <option value="">Select poster...</option>}
                              {selectedSet.movie_posters.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.title}
                                </option>
                              ))}
                            </select>
                          </div>
                        ) : selectedSet ? (
                          <span className="text-[10px] text-gray-500 shrink-0">No posters in set</span>
                        ) : (
                          <span className="text-[10px] text-gray-500 shrink-0">Select a set</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: MediUX Franchise Sets */}
          <div className="md:col-span-8 flex flex-col min-h-0">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand-400" />
              Available MediUX Franchise Sets ({mediuxSets.length})
            </h3>

            <div className="flex-1 overflow-y-auto pr-1">
              {isLoading ? (
                <div className="h-64 flex flex-col items-center justify-center text-gray-500 gap-2">
                  <RefreshCw className="w-6 h-6 animate-spin text-brand-500" />
                  <span className="text-sm">Fetching franchise sets...</span>
                </div>
              ) : mediuxSets.length === 0 ? (
                <div className="h-64 flex flex-col items-center justify-center text-gray-500 gap-2 p-6 text-center border border-dashed border-gray-800 rounded-xl">
                  <AlertCircle className="w-8 h-8 opacity-40" />
                  <p className="text-sm font-medium text-gray-400">No complete MediUX boxset found</p>
                  <p className="text-xs text-gray-500">
                    You can still style individual movie posters from the Movies tab!
                  </p>

                  {/* TMDb collection covers fallback */}
                  {tmdbPosters.length > 0 && (
                    <div className="mt-4 w-full text-left">
                      <h4 className="text-xs font-semibold text-gray-300 mb-2">TMDb Collection Boxset Posters</h4>
                      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                        {tmdbPosters.map((p, idx) => (
                          <div
                            key={p.file_path || idx}
                            className={`relative aspect-[2/3] rounded-lg overflow-hidden border-2 transition group ${
                              selectedBoxsetOnlyUrl === p.url ? 'border-brand-500' : 'border-gray-800 hover:border-gray-600'
                            }`}
                          >
                            <img
                              src={p.thumb_url || p.url}
                              alt="TMDb Cover"
                              className="w-full h-full object-cover cursor-pointer"
                              onClick={() => {
                                setSelectedBoxsetOnlyUrl(p.url);
                                setSelectedSet(null);
                              }}
                            />
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setPreviewPoster({
                                  url: p.url,
                                  title: `${collection.title} (TMDb Boxset Poster)`
                                });
                              }}
                              className="absolute top-1 right-1 p-1 rounded-md bg-black/75 text-gray-300 hover:text-white opacity-0 group-hover:opacity-100 transition shadow"
                              title="Preview larger"
                            >
                              <ZoomIn className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-6">
                  {mediuxSets.map((set) => {
                    const isSelected = selectedSet?.id === set.id;
                    return (
                      <div
                        key={set.id}
                        className={`bg-dark-950/70 border rounded-xl p-4 transition ${
                          isSelected
                            ? 'border-brand-500 ring-2 ring-brand-500/20 shadow-xl'
                            : 'border-gray-800/80 hover:border-gray-700'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-semibold text-sm text-white">{set.set_name}</h4>
                              {isSelected && (
                                <span className="bg-brand-500 text-dark-950 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                                  <Check className="w-2.5 h-2.5" /> Selected
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-gray-400 mt-0.5">
                              by <span className="text-brand-400 font-medium">{set.creator}</span>
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => {
                                setSelectedSet(set);
                                setSelectedBoxsetOnlyUrl(null);
                              }}
                              className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition ${
                                isSelected
                                  ? 'bg-brand-500 text-dark-950'
                                  : 'bg-dark-800 hover:bg-dark-750 text-white'
                              }`}
                            >
                              {isSelected ? 'Selected' : 'Select Set'}
                            </button>
                            <a
                              href={set.set_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs text-gray-400 hover:text-brand-400 p-1.5"
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>
                        </div>

                        {/* Set Preview Strip (Boxset + Movies) */}
                        <div className="flex items-center gap-3 overflow-x-auto pb-2 pt-1">
                          {set.collection_poster_url && (
                            <div
                              onClick={() =>
                                setPreviewPoster({
                                  url: set.collection_poster_url!,
                                  title: `${set.set_name} (Boxset Cover)`,
                                  subtitle: `by ${set.creator}`
                                })
                              }
                              className="relative aspect-[2/3] w-24 shrink-0 rounded-lg overflow-hidden border-2 border-brand-500/60 shadow cursor-zoom-in group/boxset hover:border-brand-400 transition"
                              title="Click to preview larger"
                            >
                              <img
                                src={set.collection_poster_url}
                                alt="Boxset"
                                className="w-full h-full object-cover transition duration-300 group-hover/boxset:scale-105"
                              />
                              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/boxset:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                                <div className="p-1.5 rounded-full bg-black/60 text-white backdrop-blur-sm">
                                  <ZoomIn className="w-4 h-4" />
                                </div>
                              </div>
                              <div className="absolute inset-x-0 bottom-0 bg-black/80 text-brand-400 text-[9px] font-bold text-center py-0.5">
                                Boxset
                              </div>
                            </div>
                          )}
                          {set.movie_posters.map((mp) => (
                            <div
                              key={mp.id}
                              onClick={() =>
                                setPreviewPoster({
                                  url: mp.url,
                                  title: mp.title,
                                  subtitle: `${set.set_name} • by ${set.creator}`
                                })
                              }
                              className="relative aspect-[2/3] w-20 shrink-0 rounded-lg overflow-hidden border border-gray-800 hover:border-gray-500 shadow cursor-zoom-in group/mp transition"
                              title="Click to preview larger"
                            >
                              <img
                                src={mp.url}
                                alt={mp.title}
                                className="w-full h-full object-cover transition duration-300 group-hover/mp:scale-105"
                              />
                              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/mp:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                                <div className="p-1 rounded-full bg-black/60 text-white backdrop-blur-sm">
                                  <ZoomIn className="w-3.5 h-3.5" />
                                </div>
                              </div>
                              <div className="absolute inset-x-0 bottom-0 bg-black/75 text-gray-300 text-[8px] truncate px-1 py-0.5 text-center">
                                {mp.title}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Enlarged Poster Lightbox Modal */}
      {previewPoster && (
        <div
          className="fixed inset-0 z-[70] bg-black/90 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 animate-fadeIn"
          onClick={() => setPreviewPoster(null)}
        >
          <div
            className="relative max-w-md sm:max-w-lg w-full flex flex-col items-center bg-dark-950/95 border border-gray-800 rounded-2xl shadow-2xl p-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header with Title & Close */}
            <div className="w-full flex items-center justify-between pb-3 mb-3 border-b border-gray-800">
              <div className="min-w-0 pr-3">
                <h4 className="text-sm sm:text-base font-bold text-white truncate" title={previewPoster.title}>
                  {previewPoster.title}
                </h4>
                {previewPoster.subtitle && (
                  <p className="text-xs text-gray-400 truncate mt-0.5">{previewPoster.subtitle}</p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <a
                  href={previewPoster.url}
                  target="_blank"
                  rel="noreferrer"
                  className="p-1.5 rounded-lg text-gray-400 hover:text-brand-400 hover:bg-dark-800 transition"
                  title="Open full resolution image in new tab"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
                <button
                  onClick={() => setPreviewPoster(null)}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-dark-800 transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Large Poster Image */}
            <div className="relative aspect-[2/3] max-h-[70vh] rounded-xl overflow-hidden shadow-2xl border border-gray-800 bg-black flex items-center justify-center">
              <img
                src={previewPoster.url}
                alt={previewPoster.title}
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
