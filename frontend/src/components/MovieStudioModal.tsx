import React, { useState, useEffect } from 'react';
import { Movie, MediuxMovieSet, TmdbPosterOption } from '../types';
import { api } from '../api';
import {
  X, Check, RefreshCw, Layers, ExternalLink, Image as ImageIcon,
  Sparkles, RotateCcw, AlertCircle, Eye, ThumbsUp, Upload
} from 'lucide-react';
import { useToast } from '../context/ToastContext';

interface MovieStudioModalProps {
  movie: Movie;
  onClose: () => void;
  onUpdated: () => void;
  testMode?: boolean;
}

export const MovieStudioModal: React.FC<MovieStudioModalProps> = ({ movie, onClose, onUpdated, testMode = false }) => {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<'mediux' | 'tmdb' | 'custom'>('mediux');
  const [isLoading, setIsLoading] = useState(true);
  const [isApplying, setIsApplying] = useState(false);
  const [isReverting, setIsReverting] = useState(false);
  const [isForceLive, setIsForceLive] = useState(false);

  const [currentPoster, setCurrentPoster] = useState<string | undefined>(movie.poster_url);
  const [selectedPosterUrl, setSelectedPosterUrl] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<'mediux' | 'tmdb' | 'custom'>('mediux');
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const [mediuxSets, setMediuxSets] = useState<MediuxMovieSet[]>([]);
  const [tmdbPosters, setTmdbPosters] = useState<TmdbPosterOption[]>([]);
  const [customUrlInput, setCustomUrlInput] = useState('');

  // Load available posters
  useEffect(() => {
    let isMounted = true;
    const loadPosters = async () => {
      setIsLoading(true);
      try {
        const data = await api.getMoviePosters(movie.rating_key);
        if (isMounted) {
          let sets = [...(data.mediux_sets || [])];
          if (sets.length > 0 && (movie.custom_poster_url || movie.poster_url)) {
            const targetUrl = movie.custom_poster_url || movie.poster_url;
            const matchedIndex = sets.findIndex(
              (s) =>
                s.poster_url === targetUrl ||
                (s.posters && s.posters.some((p) => p.url === targetUrl))
            );
            if (matchedIndex > 0) {
              const [matchedSet] = sets.splice(matchedIndex, 1);
              sets.unshift(matchedSet);
            }
          }
          setMediuxSets(sets);
          setTmdbPosters(data.tmdb_posters || []);
          if (data.current_poster) {
            setCurrentPoster(data.current_poster);
          }
          // Default tab to TMDb if no MediUX sets found
          if ((!data.mediux_sets || data.mediux_sets.length === 0) && (data.tmdb_posters && data.tmdb_posters.length > 0)) {
            setActiveTab('tmdb');
          }
        }
      } catch (err) {
        console.error('Failed to load movie posters:', err);
        showToast({ type: 'error', message: 'Failed to load poster artwork' });
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    loadPosters();
    return () => { isMounted = false; };
  }, [movie.rating_key]);

  const handleUploadPoster = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      showToast({
        type: 'error',
        message: 'Please select a valid image file (JPG, PNG, or WEBP).'
      });
      return;
    }

    setIsUploading(true);
    try {
      const res = await api.uploadMoviePoster(movie.rating_key, file);
      setSelectedPosterUrl(res.poster_url);
      setUploadedFilePath(res.file_path);
      setSelectedSource('custom');
      setUploadedFileName(file.name);
      setActiveTab('custom');
      showToast({
        type: 'success',
        message: `Poster uploaded! Click 'Apply Poster to Plex' to save.`
      });
    } catch (err: any) {
      showToast({
        type: 'error',
        message: String(err?.message || err)
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleApplyPoster = async () => {
    if (!selectedPosterUrl) return;
    setIsApplying(true);
    try {
      const res = await api.applyMoviePoster(
        movie.rating_key,
        selectedPosterUrl,
        selectedSource,
        isForceLive,
        uploadedFilePath || undefined
      );
      if (res.test_mode) {
        showToast({
          type: 'info',
          message: '🧪 Test Mode: Saved poster locally to cache/test_output/. Check "Live Upload" to push to Plex.'
        });
      } else {
        showToast({ type: 'success', message: 'Poster applied successfully to Plex!' });
        setCurrentPoster(res.poster_url);
        setSelectedPosterUrl(null);
        setUploadedFilePath(null);
        setUploadedFileName(null);
        onUpdated();
      }
    } catch (err: any) {
      showToast({ type: 'error', message: err.message || 'Failed to apply poster' });
    } finally {
      setIsApplying(false);
    }
  };

  const handleRevert = async () => {
    if (!window.confirm('Revert poster to Plex original default?')) return;
    setIsReverting(true);
    try {
      const res = await api.revertMoviePoster(movie.rating_key, isForceLive);
      if (res.test_mode) {
        showToast({
          type: 'info',
          message: '🧪 Test Mode: Skipped reverting in Plex. Check "Live Upload" to execute.'
        });
      } else {
        showToast({ type: 'success', message: 'Reverted to original Plex poster' });
        setCurrentPoster(`/api/movies/${movie.rating_key}/poster.jpg?t=${Date.now()}`);
        setSelectedPosterUrl(null);
        setUploadedFilePath(null);
        setUploadedFileName(null);
        onUpdated();
      }
    } catch (err: any) {
      showToast({ type: 'error', message: err.message || 'Failed to revert poster' });
    } finally {
      setIsReverting(false);
    }
  };

  const activeDisplayPoster = selectedPosterUrl || currentPoster;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-2 sm:p-4 overflow-y-auto">
      <div className="bg-dark-900 border border-gray-800 rounded-2xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-fadeIn">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-gray-800 flex items-center justify-between gap-4 bg-dark-950/60">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg sm:text-xl font-bold text-white truncate" title={movie.title}>
                {movie.title}
              </h2>
              {movie.year && (
                <span className="text-sm font-medium text-gray-400">({movie.year})</span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-400 mt-1">
              {movie.collection_name && (
                <span className="inline-flex items-center gap-1 text-brand-400 bg-brand-950/60 border border-brand-500/30 px-2 py-0.5 rounded-full">
                  <Layers className="w-3 h-3" />
                  {movie.collection_name}
                </span>
              )}
              {movie.tmdb_id && (
                <a
                  href={`https://www.themoviedb.org/movie/${movie.tmdb_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-brand-400 transition flex items-center gap-0.5"
                >
                  TMDb: {movie.tmdb_id} <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
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
              className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-dark-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Left Column: Preview & Controls */}
          <div className="md:col-span-4 flex flex-col items-center gap-4">
            <div className="w-full max-w-[280px]">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragOver(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) handleUploadPoster(file);
                }}
                className={`relative aspect-[2/3] rounded-xl overflow-hidden border-2 bg-dark-950 shadow-xl group transition-all ${
                  isDragOver
                    ? 'border-dashed border-brand-400 bg-brand-500/10 ring-2 ring-brand-400/40'
                    : 'border-gray-700'
                }`}
              >
                {isDragOver && (
                  <div className="absolute inset-0 bg-dark-950/85 backdrop-blur-sm z-20 flex flex-col items-center justify-center gap-2 text-brand-300 p-4 text-center pointer-events-none">
                    <Upload className="w-8 h-8 animate-bounce text-brand-400" />
                    <span className="text-xs font-bold">Drop image here to upload</span>
                  </div>
                )}
                {isUploading && (
                  <div className="absolute inset-0 bg-dark-950/85 backdrop-blur-sm z-20 flex flex-col items-center justify-center gap-2 text-brand-400 p-4 text-center pointer-events-none">
                    <RefreshCw className="w-8 h-8 animate-spin" />
                    <span className="text-xs font-semibold">Uploading & processing...</span>
                  </div>
                )}
                {activeDisplayPoster ? (
                  <img
                    src={activeDisplayPoster}
                    alt={movie.title}
                    className="w-full h-full object-cover transition duration-300"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-gray-500">
                    <ImageIcon className="w-10 h-10 mb-2 opacity-50" />
                    <span className="text-xs">No poster available</span>
                  </div>
                )}

                {selectedPosterUrl ? (
                  <div className="absolute top-2 left-2 bg-brand-500 text-dark-950 text-xs font-bold px-2.5 py-1 rounded-full shadow flex items-center gap-1">
                    <Sparkles className="w-3 h-3" /> Previewing Selection
                  </div>
                ) : (
                  <div className="absolute top-2 left-2 bg-black/70 backdrop-blur-md text-gray-300 text-[11px] font-semibold px-2 py-0.5 rounded shadow border border-white/10">
                    Current Poster
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="mt-4 flex flex-col gap-2">
                <button
                  onClick={handleApplyPoster}
                  disabled={!selectedPosterUrl || isApplying}
                  className="w-full py-2.5 px-4 bg-brand-500 hover:bg-brand-400 disabled:opacity-40 disabled:cursor-not-allowed text-dark-950 font-bold rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20 transition"
                >
                  {isApplying ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Check className="w-4 h-4" />
                  )}
                  {isApplying ? 'Applying to Plex...' : 'Apply Poster to Plex'}
                </button>

                {selectedPosterUrl && (
                  <button
                    onClick={() => setSelectedPosterUrl(null)}
                    className="w-full py-2 px-3 bg-dark-800 hover:bg-dark-750 text-gray-300 hover:text-white rounded-xl text-xs font-medium transition"
                  >
                    Cancel Selection
                  </button>
                )}

                <button
                  onClick={handleRevert}
                  disabled={isReverting}
                  className="w-full py-2 px-3 bg-dark-850 hover:bg-dark-800 border border-gray-800 hover:border-gray-700 text-gray-400 hover:text-red-400 rounded-xl text-xs flex items-center justify-center gap-1.5 transition mt-1"
                  title="Revert to original Plex poster"
                >
                  <RotateCcw className={`w-3.5 h-3.5 ${isReverting ? 'animate-spin' : ''}`} />
                  Revert to Default
                </button>
              </div>

              {/* Movie Synopsis */}
              {movie.summary && (
                <div className="mt-4 p-3 rounded-xl bg-dark-950/60 border border-gray-800/80 text-xs text-gray-400 max-h-36 overflow-y-auto">
                  <span className="font-semibold text-gray-300 block mb-1">Overview</span>
                  {movie.summary}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Poster Selection Tabs */}
          <div className="md:col-span-8 flex flex-col min-h-0">
            {/* Tabs Header */}
            <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
              <button
                onClick={() => setActiveTab('mediux')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${
                  activeTab === 'mediux'
                    ? 'bg-brand-500/10 text-brand-400 border border-brand-500/30'
                    : 'text-gray-400 hover:text-white hover:bg-dark-800'
                }`}
              >
                <Sparkles className="w-4 h-4" />
                MediUX Sets ({mediuxSets.length})
              </button>

              <button
                onClick={() => setActiveTab('tmdb')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${
                  activeTab === 'tmdb'
                    ? 'bg-brand-500/10 text-brand-400 border border-brand-500/30'
                    : 'text-gray-400 hover:text-white hover:bg-dark-800'
                }`}
              >
                <ImageIcon className="w-4 h-4" />
                TMDb Gallery ({tmdbPosters.length})
              </button>

              <button
                onClick={() => setActiveTab('custom')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${
                  activeTab === 'custom'
                    ? 'bg-brand-500/10 text-brand-400 border border-brand-500/30'
                    : 'text-gray-400 hover:text-white hover:bg-dark-800'
                }`}
              >
                <Upload className="w-4 h-4" />
                Upload / Custom
              </button>
            </div>

            {/* Tab Contents */}
            <div className="flex-1 overflow-y-auto mt-4 pr-1">
              {isLoading ? (
                <div className="h-64 flex flex-col items-center justify-center text-gray-500 gap-2">
                  <RefreshCw className="w-6 h-6 animate-spin text-brand-500" />
                  <span className="text-sm">Fetching posters from MediUX & TMDb...</span>
                </div>
              ) : activeTab === 'mediux' ? (
                /* MediUX Sets */
                mediuxSets.length === 0 ? (
                  <div className="h-64 flex flex-col items-center justify-center text-gray-500 gap-2 p-6 text-center border border-dashed border-gray-800 rounded-xl">
                    <AlertCircle className="w-8 h-8 opacity-40" />
                    <p className="text-sm font-medium text-gray-400">No MediUX sets found for this movie</p>
                    <p className="text-xs text-gray-500">Check the TMDb Gallery tab for official and textless posters!</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-6">
                    {mediuxSets.map((set) => (
                      <div key={set.id} className="bg-dark-950/70 border border-gray-800/80 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="font-semibold text-sm text-white">{set.set_name}</h4>
                            <p className="text-xs text-gray-400 mt-0.5">
                              by <span className="text-brand-400 font-medium">{set.creator}</span>
                              {set.date_updated && <span> • updated {new Date(set.date_updated).toLocaleDateString()}</span>}
                            </p>
                          </div>
                          <a
                            href={set.set_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-gray-400 hover:text-brand-400 flex items-center gap-1 transition"
                          >
                            View on MediUX <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>

                        {/* Posters in this set */}
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                          {set.posters.map((p) => {
                            const isSelected = selectedPosterUrl === p.url;
                            return (
                              <div
                                key={p.id}
                                onClick={() => {
                                  setSelectedPosterUrl(p.url);
                                  setSelectedSource('mediux');
                                }}
                                className={`group relative aspect-[2/3] rounded-lg overflow-hidden cursor-pointer border-2 transition transform hover:scale-[1.02] ${
                                  isSelected
                                    ? 'border-brand-500 shadow-lg shadow-brand-500/20 ring-2 ring-brand-500/40'
                                    : 'border-gray-800 hover:border-gray-600'
                                }`}
                              >
                                <img src={p.url} alt={p.title} className="w-full h-full object-cover" loading="lazy" />
                                {isSelected && (
                                  <div className="absolute top-1.5 right-1.5 bg-brand-500 text-dark-950 p-1 rounded-full shadow">
                                    <Check className="w-3 h-3 stroke-[3]" />
                                  </div>
                                )}
                                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-2 opacity-0 group-hover:opacity-100 transition flex items-end justify-between">
                                  <span className="text-[10px] text-white font-medium truncate">{p.title}</span>
                                  <Eye className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              ) : activeTab === 'tmdb' ? (
                /* TMDb Gallery */
                tmdbPosters.length === 0 ? (
                  <div className="h-64 flex flex-col items-center justify-center text-gray-500 gap-2 p-6 text-center border border-dashed border-gray-800 rounded-xl">
                    <AlertCircle className="w-8 h-8 opacity-40" />
                    <p className="text-sm font-medium text-gray-400">No posters found on TMDb</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                    {tmdbPosters.map((p, idx) => {
                      const isSelected = selectedPosterUrl === p.url;
                      return (
                        <div
                          key={p.file_path || idx}
                          onClick={() => {
                            setSelectedPosterUrl(p.url);
                            setSelectedSource('tmdb');
                          }}
                          className={`group relative aspect-[2/3] rounded-lg overflow-hidden cursor-pointer border-2 transition transform hover:scale-[1.02] ${
                            isSelected
                              ? 'border-brand-500 shadow-lg shadow-brand-500/20 ring-2 ring-brand-500/40'
                              : 'border-gray-800 hover:border-gray-600'
                          }`}
                        >
                          <img src={p.thumb_url || p.url} alt={`TMDb poster ${idx}`} className="w-full h-full object-cover" loading="lazy" />

                          {/* Textless Badge */}
                          {p.is_textless && (
                            <div className="absolute top-1.5 left-1.5 bg-purple-950/85 backdrop-blur-md text-purple-300 border border-purple-500/40 text-[9px] font-semibold px-1.5 py-0.5 rounded shadow">
                              Textless
                            </div>
                          )}

                          {isSelected && (
                            <div className="absolute top-1.5 right-1.5 bg-brand-500 text-dark-950 p-1 rounded-full shadow">
                              <Check className="w-3 h-3 stroke-[3]" />
                            </div>
                          )}

                          {/* Vote overlay */}
                          {p.vote_count ? (
                            <div className="absolute bottom-1.5 left-1.5 bg-black/75 backdrop-blur-md text-gray-300 text-[9px] px-1.5 py-0.5 rounded flex items-center gap-1 border border-white/10">
                              <ThumbsUp className="w-2.5 h-2.5 text-brand-400" />
                              {p.vote_count}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                )
              ) : (
                /* Upload & Custom Direct URL */
                <div className="flex flex-col gap-5">
                  {/* Upload Dropzone */}
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragOver(true);
                    }}
                    onDragLeave={() => setIsDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragOver(false);
                      const file = e.dataTransfer.files?.[0];
                      if (file) handleUploadPoster(file);
                    }}
                    className={`bg-dark-950/80 border-2 rounded-2xl p-6 sm:p-8 flex flex-col items-center justify-center text-center transition-all ${
                      isDragOver
                        ? 'border-dashed border-brand-400 bg-brand-500/10 ring-2 ring-brand-400/30'
                        : 'border-dashed border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <div className="w-12 h-12 rounded-2xl bg-dark-850 border border-gray-800 flex items-center justify-center text-brand-400 mb-3 shadow-inner">
                      {isUploading ? (
                        <RefreshCw className="w-6 h-6 animate-spin" />
                      ) : (
                        <Upload className="w-6 h-6" />
                      )}
                    </div>
                    <h4 className="text-sm font-bold text-white mb-1">
                      {isUploading ? 'Uploading & processing poster...' : 'Upload Custom Poster'}
                    </h4>
                    <p className="text-xs text-gray-400 max-w-sm mb-4">
                      Drag and drop your poster image here, or click to browse. Supports JPG, PNG, and WEBP.
                    </p>

                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="px-4 py-2 rounded-xl bg-brand-500 hover:bg-brand-400 text-dark-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-brand-500/20 transition disabled:opacity-50"
                    >
                      <Upload className="w-3.5 h-3.5" />
                      <span>{isUploading ? 'Uploading...' : 'Choose Poster File'}</span>
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadPoster(file);
                        if (fileInputRef.current) fileInputRef.current.value = '';
                      }}
                    />

                    {uploadedFileName && selectedPosterUrl && (
                      <div className="mt-4 px-3 py-2 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-400 text-xs flex items-center gap-2">
                        <Check className="w-4 h-4 text-emerald-400" />
                        <span>Ready to apply: <strong>{uploadedFileName}</strong></span>
                      </div>
                    )}
                  </div>

                  {/* Or Direct Image URL */}
                  <div className="bg-dark-950/70 border border-gray-800 rounded-xl p-4 sm:p-5 flex flex-col gap-3">
                    <div className="flex items-center gap-2">
                      <ExternalLink className="w-4 h-4 text-gray-400" />
                      <label className="text-xs font-semibold text-gray-200">Or Paste Image URL</label>
                    </div>
                    <div className="flex gap-2">
                      <input
                        type="url"
                        placeholder="https://example.com/poster.jpg"
                        value={customUrlInput}
                        onChange={(e) => setCustomUrlInput(e.target.value)}
                        className="flex-1 bg-dark-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500"
                      />
                      <button
                        onClick={() => {
                          if (customUrlInput.trim()) {
                            setSelectedPosterUrl(customUrlInput.trim());
                            setUploadedFilePath(null);
                            setUploadedFileName(null);
                            setSelectedSource('custom');
                          }
                        }}
                        className="bg-dark-800 hover:bg-dark-750 text-gray-200 border border-gray-700 font-semibold px-4 py-2 rounded-xl text-xs transition"
                      >
                        Preview
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
