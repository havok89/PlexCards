import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Show, Episode, MediuxSet, CandidateStill } from '../../types';
import { api } from '../../api';
import { useToast } from '../../context/ToastContext';
import {
  Eye, Zap, Wand2, Loader2, Sparkles, FlaskConical,
  Tv, Split, SlidersHorizontal, ChevronLeft, ChevronRight,
  Film, Check, Send
} from 'lucide-react';

interface StudioPreviewCanvasProps {
  show: Show;
  episodes: Episode[];
  selectedEpIndex: number;
  onSelectEpIndex: (index: number) => void;
  isEpisodesLoading: boolean;
  activeDisplayUrl: string | null;
  previewTab: 'mediux' | 'generator';
  onSetPreviewTab: (tab: 'mediux' | 'generator') => void;
  currentEpMediuxCardUrl?: string;
  isShowingMediux: boolean;
  activeMediuxSet?: MediuxSet | null;
  isPreviewLoading: boolean;
  previewUrl: string | null;
  currentEp?: Episode;
  hasGeminiKey?: boolean;
  onStillChanged?: () => void;
  onApplySingleCard?: () => void;
  isApplyingSingle?: boolean;
  testMode?: boolean;
  isForceLive?: boolean;
}

export const StudioPreviewCanvas: React.FC<StudioPreviewCanvasProps> = ({
  show,
  episodes,
  selectedEpIndex,
  onSelectEpIndex,
  isEpisodesLoading,
  activeDisplayUrl,
  previewTab,
  onSetPreviewTab,
  currentEpMediuxCardUrl,
  isShowingMediux,
  activeMediuxSet,
  isPreviewLoading,
  previewUrl,
  currentEp,
  hasGeminiKey = true,
  onStillChanged,
  onApplySingleCard,
  isApplyingSingle,
  testMode,
  isForceLive
}) => {
  const { showToast } = useToast();

  // Modes: 'single' card or 'shelf' (2 in a row simulator)
  const [viewMode, setViewMode] = useState<'single' | 'shelf'>('single');

  // Candidate TMDb stills
  const [candidateStills, setCandidateStills] = useState<CandidateStill[]>([]);
  const [selectedStillPath, setSelectedStillPath] = useState<string | null>(null);
  const [isStillsLoading, setIsStillsLoading] = useState<boolean>(false);
  const [isAutoPicking, setIsAutoPicking] = useState<boolean>(false);

  // Before/After comparison slider
  const [isCompareMode, setIsCompareMode] = useState<boolean>(false);
  const [splitPos, setSplitPos] = useState<number>(50); // percentage 0-100
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [rawStillUrl, setRawStillUrl] = useState<string | null>(null);
  const [isRawStillLoading, setIsRawStillLoading] = useState<boolean>(false);
  const splitContainerRef = useRef<HTMLDivElement>(null);

  // Fetch candidate stills from TMDb when episode or show changes
  useEffect(() => {
    if (!currentEp || !show.tmdb_id) {
      setCandidateStills([]);
      setSelectedStillPath(null);
      return;
    }

    let active = true;
    setIsStillsLoading(true);

    api
      .getCandidateStills(show.rating_key, currentEp.season_number, currentEp.episode_number)
      .then((data) => {
        if (!active) return;
        setCandidateStills(data.stills || []);
        setSelectedStillPath(data.selected_still_path);
        setIsStillsLoading(false);
      })
      .catch((err) => {
        console.warn('Candidate stills fetch error:', err);
        if (active) setIsStillsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [show.rating_key, show.tmdb_id, currentEp?.season_number, currentEp?.episode_number]);

  const handleSelectStill = async (still: CandidateStill) => {
    if (!currentEp) return;
    setSelectedStillPath(still.file_path);
    try {
      await api.selectEpisodeStill(
        show.rating_key,
        currentEp.season_number,
        currentEp.episode_number,
        still.file_path
      );
      showToast({
        type: 'success',
        title: 'Frame Selection Saved',
        message: `Selected frame for S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')} saved.`
      });
      // Invalidate raw still cache for split comparison
      setRawStillUrl(null);
      onStillChanged?.();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Failed to Save Frame',
        message: String(err?.message || err)
      });
    }
  };

  const handleAutoPick = async () => {
    if (!currentEp) return;
    setIsAutoPicking(true);
    try {
      const res = await api.autoPickStills(show.rating_key, currentEp.season_number);
      showToast({
        type: 'success',
        title: 'Smart Auto-Pick Complete',
        message: res.message || `Selected highest rated stills for Season ${currentEp.season_number}.`
      });
      const data = await api.getCandidateStills(
        show.rating_key,
        currentEp.season_number,
        currentEp.episode_number
      );
      setCandidateStills(data.stills || []);
      setSelectedStillPath(data.selected_still_path);
      setRawStillUrl(null);
      onStillChanged?.();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Auto-Pick Failed',
        message: String(err?.message || err)
      });
    } finally {
      setIsAutoPicking(false);
    }
  };

  // Fetch raw still when compare mode is activated or episode changes
  useEffect(() => {
    if (!isCompareMode || !currentEp) return;

    let active = true;
    setIsRawStillLoading(true);

    api
      .getRawStillBlob(show.rating_key, currentEp.season_number, currentEp.episode_number)
      .then((blob) => {
        if (!active) return;
        const url = URL.createObjectURL(blob);
        setRawStillUrl(url);
        setIsRawStillLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load raw still for compare:', err);
        if (active) setIsRawStillLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isCompareMode, currentEp?.season_number, currentEp?.episode_number, show.rating_key, selectedStillPath]);

  // Handle drag for split comparison slider
  const handlePointerMove = useCallback(
    (clientX: number) => {
      if (!splitContainerRef.current) return;
      const rect = splitContainerRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const pct = Math.max(0, Math.min(100, (x / rect.width) * 100));
      setSplitPos(pct);
    },
    []
  );

  useEffect(() => {
    if (!isDragging) return;

    const onMouseMove = (e: MouseEvent) => handlePointerMove(e.clientX);
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        handlePointerMove(e.touches[0].clientX);
      }
    };
    const onEnd = () => setIsDragging(false);

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onEnd);
    window.addEventListener('touchmove', onTouchMove);
    window.addEventListener('touchend', onEnd);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onEnd);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onEnd);
    };
  }, [isDragging, handlePointerMove]);

  // Calculate 2-in-a-row episodes window (4 episodes in a 2x2 grid) centered around selectedEpIndex
  const shelfWindowSize = 4;
  let shelfStartIndex = 0;
  if (episodes.length > shelfWindowSize) {
    const pairStart = Math.floor(selectedEpIndex / 2) * 2;
    shelfStartIndex = Math.max(
      0,
      Math.min(pairStart, episodes.length - shelfWindowSize)
    );
  }
  const shelfEpisodes = episodes.slice(shelfStartIndex, shelfStartIndex + shelfWindowSize);

  return (
    <div className="w-full lg:col-span-7 p-3 sm:p-5 lg:p-6 flex flex-col gap-3 sm:gap-4 bg-dark-950/40 shrink-0 lg:shrink lg:overflow-y-auto min-h-0">
      {/* Top Header Controls */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          {/* View Mode: Single vs 2-in-a-Row TV Shelf */}
          <div className="flex items-center bg-dark-800 p-0.5 rounded-lg border border-gray-700 text-[11px]">
            <button
              type="button"
              onClick={() => setViewMode('single')}
              className={`px-2 py-0.5 rounded-md font-medium transition flex items-center gap-1 ${
                viewMode === 'single'
                  ? 'bg-brand-500 text-white shadow'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Eye className="w-3 h-3" />
              Card
            </button>
            <button
              type="button"
              onClick={() => {
                setViewMode('shelf');
                setIsCompareMode(false);
              }}
              className={`px-2 py-0.5 rounded-md font-medium transition flex items-center gap-1 ${
                viewMode === 'shelf'
                  ? 'bg-brand-500 text-white shadow'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Tv className="w-3 h-3" />
              2-in-a-Row Shelf
            </button>
          </div>

          {/* Before / After Compare Toggle (Only in single card view) */}
          {viewMode === 'single' && (
            <button
              type="button"
              onClick={() => setIsCompareMode(!isCompareMode)}
              className={`px-2 py-1 rounded-lg border text-[11px] font-medium flex items-center gap-1.5 transition ${
                isCompareMode
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50'
                  : 'bg-dark-800 text-gray-400 border-gray-700 hover:text-gray-200'
              }`}
              title="Compare rendered title card side-by-side with the original raw episode still"
            >
              <Split className="w-3 h-3 text-cyan-400" />
              Compare Raw
            </button>
          )}

          {/* View Switcher: MediUX Card vs Generator Fallback */}
          {currentEpMediuxCardUrl && show.mode === 'auto' && viewMode === 'single' && (
            <div className="flex items-center bg-dark-800 p-0.5 rounded-lg border border-gray-700 text-[11px]">
              <button
                type="button"
                onClick={() => onSetPreviewTab('mediux')}
                className={`px-2 py-0.5 rounded-md font-medium transition flex items-center gap-1 ${
                  previewTab === 'mediux'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <Zap className="w-3 h-3 text-emerald-400" />
                MediUX
              </button>
              <button
                type="button"
                onClick={() => onSetPreviewTab('generator')}
                className={`px-2 py-0.5 rounded-md font-medium transition flex items-center gap-1 ${
                  previewTab === 'generator'
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                <Wand2 className="w-3 h-3 text-purple-400" />
                Generator
              </button>
            </div>
          )}
        </div>

        {/* Episode Picker with Loading Spinner */}
        <div className="flex items-center gap-2">
          {isEpisodesLoading ? (
            <div className="flex items-center gap-2 text-xs text-gray-400 bg-dark-800 border border-gray-700 px-3 py-1.5 rounded-lg">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-500" />
              <span>Loading episodes...</span>
            </div>
          ) : (
            <select
              value={selectedEpIndex}
              onChange={(e) => onSelectEpIndex(Number(e.target.value))}
              className="bg-dark-800 border border-gray-700 text-xs rounded-lg px-2.5 py-1.5 text-gray-300 focus:outline-none focus:border-brand-500 max-w-[180px] sm:max-w-xs truncate"
            >
              {episodes.map((ep, idx) => (
                <option key={ep.rating_key} value={idx}>
                  S{String(ep.season_number).padStart(2, '0')}E
                  {String(ep.episode_number).padStart(2, '0')} - {ep.title}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Main Preview Area */}
      {viewMode === 'shelf' ? (
        /* 2-in-a-Row TV Grid Shelf Simulator */
        <div className="flex flex-col gap-3 bg-dark-900 border border-gray-800 rounded-xl p-3 sm:p-4 shadow-2xl">
          <div className="flex items-center justify-between border-b border-gray-800/80 pb-2.5 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500/80 animate-pulse" />
              <span className="text-xs font-semibold text-gray-200 uppercase tracking-wider">
                2-in-a-Row Shelf Simulator
              </span>
              <span className="text-[10px] text-gray-400 bg-dark-800 px-1.5 py-0.5 rounded border border-gray-700">
                Side-by-Side View
              </span>
            </div>

            {/* Pagination Controls */}
            {episodes.length > 2 && (
              <div className="flex items-center gap-1.5 text-[11px]">
                <button
                  type="button"
                  disabled={selectedEpIndex <= 0}
                  onClick={() => onSelectEpIndex(Math.max(0, selectedEpIndex - 2))}
                  className="px-2 py-0.5 rounded bg-dark-800 border border-gray-700 text-gray-300 hover:text-white disabled:opacity-30 disabled:pointer-events-none flex items-center gap-0.5 transition"
                  title="Previous 2 episodes"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  <span>Prev</span>
                </button>
                <span className="text-[10px] text-gray-400 font-mono px-1">
                  {selectedEpIndex + 1}/{episodes.length}
                </span>
                <button
                  type="button"
                  disabled={selectedEpIndex >= episodes.length - 1}
                  onClick={() => onSelectEpIndex(Math.min(episodes.length - 1, selectedEpIndex + 2))}
                  className="px-2 py-0.5 rounded bg-dark-800 border border-gray-700 text-gray-300 hover:text-white disabled:opacity-30 disabled:pointer-events-none flex items-center gap-0.5 transition"
                  title="Next 2 episodes"
                >
                  <span>Next</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* 2-in-a-Row Grid */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 py-1">
            {shelfEpisodes.map((ep, localIdx) => {
              const actualIdx = shelfStartIndex + localIdx;
              const isSelected = actualIdx === selectedEpIndex;

              return (
                <div
                  key={ep.rating_key}
                  onClick={() => onSelectEpIndex(actualIdx)}
                  className={`group cursor-pointer flex flex-col gap-1.5 transition-all duration-200 ${
                    isSelected ? 'scale-[1.01]' : 'opacity-80 hover:opacity-100'
                  }`}
                >
                  <div
                    className={`relative aspect-video rounded-xl overflow-hidden bg-dark-950 border transition-all ${
                      isSelected
                        ? 'border-brand-500 shadow-xl shadow-brand-500/25 ring-2 ring-brand-500/60'
                        : 'border-gray-800 group-hover:border-gray-600'
                    }`}
                  >
                    {isSelected && activeDisplayUrl ? (
                      <img
                        src={activeDisplayUrl}
                        alt={ep.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <img
                        src={`/api/shows/${show.rating_key}/raw-still?season_number=${ep.season_number}&episode_number=${ep.episode_number}`}
                        alt={ep.title}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    )}

                    {/* Active Focus Pill */}
                    {isSelected && (
                      <div className="absolute top-1.5 left-1.5 bg-brand-600 text-white text-[10px] font-bold px-2 py-0.5 rounded shadow-md flex items-center gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                        ACTIVE
                      </div>
                    )}

                    {/* Episode code chip */}
                    <div className="absolute bottom-1.5 right-1.5 bg-dark-950/85 backdrop-blur-sm text-gray-200 text-[10px] font-mono px-1.5 py-0.5 rounded border border-gray-700/60 shadow">
                      S{String(ep.season_number).padStart(2, '0')}E{String(ep.episode_number).padStart(2, '0')}
                    </div>
                  </div>

                  <div className="flex flex-col px-0.5">
                    <span
                      className={`text-xs font-semibold truncate ${
                        isSelected ? 'text-brand-400' : 'text-gray-200'
                      }`}
                      title={ep.title}
                    >
                      {ep.title}
                    </span>
                    <span className="text-[10px] text-gray-400">
                      Season {ep.season_number} • Episode {ep.episode_number}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="bg-dark-950/80 border border-gray-800/80 rounded-lg p-2.5 text-[11px] text-gray-400 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <SlidersHorizontal className="w-3.5 h-3.5 text-brand-400 shrink-0" />
              <span>Side-by-side verification (2 in a row). Check text legibility, size, and layout consistency.</span>
            </span>
            <span className="text-[10px] text-gray-400 shrink-0">Click any card to select</span>
          </div>
        </div>
      ) : (
        /* Single Card View (with optional Interactive Before/After Split Comparison) */
        <div className="w-full flex justify-center shrink-0">
          <div
            ref={splitContainerRef}
            onMouseDown={(e) => {
              if (isCompareMode) {
                setIsDragging(true);
                handlePointerMove(e.clientX);
              }
            }}
            onTouchStart={(e) => {
              if (isCompareMode && e.touches.length > 0) {
                setIsDragging(true);
                handlePointerMove(e.touches[0].clientX);
              }
            }}
            className={`relative aspect-video w-full max-w-[340px] sm:max-w-[460px] lg:max-w-none bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl flex items-center justify-center select-none ${
              isCompareMode ? 'cursor-ew-resize' : ''
            }`}
          >
            {isCompareMode ? (
              /* Before / After Split Slider Mode */
              <>
                {/* Base Underlayer: Raw Episode Still */}
                {rawStillUrl ? (
                  <img
                    src={rawStillUrl}
                    alt="Raw Episode Still"
                    className="w-full h-full object-cover"
                    draggable={false}
                  />
                ) : isRawStillLoading ? (
                  <div className="flex flex-col items-center justify-center text-gray-400 text-xs gap-2">
                    <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
                    <span>Loading original raw still...</span>
                  </div>
                ) : (
                  <div className="text-gray-400 text-xs">No raw still available</div>
                )}

                {/* Overlay Layer: Rendered Plex Card with clip-path */}
                {activeDisplayUrl && (
                  <div
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    style={{
                      clipPath: `polygon(0 0, ${splitPos}% 0, ${splitPos}% 100%, 0 100%)`
                    }}
                  >
                    <img
                      src={activeDisplayUrl}
                      alt="Rendered Plex Card"
                      className="w-full h-full object-cover"
                      draggable={false}
                    />
                  </div>
                )}

                {/* Draggable Vertical Split Divider Line */}
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-white shadow-2xl pointer-events-none z-10"
                  style={{ left: `${splitPos}%` }}
                >
                  {/* Glowing Center Handle with Arrows */}
                  <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-dark-950/90 border-2 border-white shadow-xl flex items-center justify-center text-white text-[10px] font-bold">
                    ⇄
                  </div>
                </div>

                {/* Left/Right Identification Badges */}
                <div className="absolute top-2.5 left-2.5 bg-dark-950/90 backdrop-blur-md px-2 py-0.5 rounded-full border border-brand-500/50 text-brand-300 text-[10px] font-bold shadow z-20 pointer-events-none">
                  PLEX CARD ({Math.round(splitPos)}%)
                </div>
                <div className="absolute top-2.5 right-2.5 bg-dark-950/90 backdrop-blur-md px-2 py-0.5 rounded-full border border-cyan-500/50 text-cyan-300 text-[10px] font-bold shadow z-20 pointer-events-none">
                  RAW STILL ({Math.round(100 - splitPos)}%)
                </div>

                {/* Interactive Drag Hint */}
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/70 backdrop-blur-sm px-2.5 py-0.5 rounded-full text-white text-[9px] tracking-wide pointer-events-none z-20">
                  Drag slider horizontally to compare
                </div>
              </>
            ) : (
              /* Standard Preview Mode */
              <>
                {activeDisplayUrl ? (
                  <img
                    src={activeDisplayUrl}
                    alt="Title Card Preview"
                    className="w-full h-full object-cover"
                  />
                ) : isEpisodesLoading && !show.has_custom_style && hasGeminiKey ? (
                  <div className="flex flex-col items-center justify-center text-center p-6 gap-3 max-w-sm">
                    <div className="relative">
                      <Loader2 className="w-9 h-9 animate-spin text-purple-400" />
                      <Sparkles className="w-4 h-4 text-brand-400 absolute -top-1 -right-1 animate-pulse" />
                    </div>
                    <div>
                      <span className="font-semibold text-white text-sm block mb-1">
                        Styling with Gemini AI & Fetching Stills...
                      </span>
                      <span className="text-gray-400 text-xs leading-relaxed block">
                        Analyzing {show.title}&apos;s genres & tone while TMDb downloads 1080p backdrop stills.
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center text-gray-400 text-xs gap-3">
                    <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
                    <span>Loading episode still & rendering preview...</span>
                  </div>
                )}

                {/* Source Badge Overlay */}
                {activeDisplayUrl && isShowingMediux && (
                  <div className="absolute top-2 sm:top-3 left-2 sm:left-3 bg-dark-950/85 backdrop-blur-md px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full border border-emerald-500/50 text-emerald-300 text-[10px] sm:text-[11px] font-medium flex items-center gap-1 sm:gap-1.5 shadow">
                    <Zap className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-emerald-400" />
                    <span>MediUX Card • {activeMediuxSet?.creator}</span>
                  </div>
                )}

                {activeDisplayUrl && !isShowingMediux && currentEpMediuxCardUrl && show.mode === 'auto' && (
                  <div className="absolute top-2 sm:top-3 left-2 sm:left-3 bg-dark-950/85 backdrop-blur-md px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full border border-purple-500/50 text-purple-300 text-[10px] sm:text-[11px] font-medium flex items-center gap-1 sm:gap-1.5 shadow">
                    <Wand2 className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-purple-400" />
                    <span>Generator Preview (Fallback)</span>
                  </div>
                )}

                {activeDisplayUrl && show.mode === 'auto' && !currentEpMediuxCardUrl && (
                  <div className="absolute top-2 sm:top-3 left-2 sm:left-3 bg-dark-950/85 backdrop-blur-md px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full border border-amber-500/50 text-amber-300 text-[10px] sm:text-[11px] font-medium flex items-center gap-1 sm:gap-1.5 shadow">
                    <FlaskConical className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-amber-400" />
                    <span>Generator Interim Fallback</span>
                  </div>
                )}

                {/* Subdued overlay indicator when rendering new style changes */}
                {isPreviewLoading && previewUrl && !isShowingMediux && (
                  <div className="absolute top-2 sm:top-3 right-2 sm:right-3 bg-dark-950/80 backdrop-blur-md px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full border border-gray-700 text-gray-300 text-[10px] sm:text-[11px] flex items-center gap-1 sm:gap-1.5 shadow">
                    <Loader2 className="w-3 h-3 animate-spin text-brand-500" />
                    <span>Updating...</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Candidate Stills Strip (Magic Frame Carousel - Generator View Only) */}
      {currentEp && (Boolean(show.tmdb_id) || Boolean(show.tvdb_id)) && !isShowingMediux && (
        <div className="bg-dark-900 border border-gray-800 rounded-xl p-3 flex flex-col gap-2.5 shrink-0">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Film className="w-3.5 h-3.5 text-brand-400" />
              <span className="text-xs font-semibold text-gray-200">
                Candidate Stills ({candidateStills.length})
              </span>
              <span className="text-[10px] text-gray-500">
                Click any frame to auto-save
              </span>
            </div>

            <button
              type="button"
              onClick={handleAutoPick}
              disabled={isAutoPicking || candidateStills.length === 0}
              className="px-2.5 py-1 rounded-lg bg-dark-800 hover:bg-dark-700 border border-purple-500/40 text-purple-300 hover:text-purple-200 text-[11px] font-medium flex items-center gap-1.5 transition disabled:opacity-40"
              title={`Smart auto-pick the highest community-rated frame for Season ${currentEp.season_number}`}
            >
              {isAutoPicking ? (
                <Loader2 className="w-3 h-3 animate-spin text-purple-400" />
              ) : (
                <Sparkles className="w-3 h-3 text-purple-400" />
              )}
              <span>Smart Auto-Pick (Season {currentEp.season_number})</span>
            </button>
          </div>

          {/* Stills Horizontal Carousel */}
          {isStillsLoading ? (
            <div className="flex items-center justify-center py-4 text-xs text-gray-400 gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
              <span>Loading candidate stills...</span>
            </div>
          ) : candidateStills.length === 0 ? (
            <div className="text-[11px] text-gray-500 italic py-1">
              No candidate stills available for this episode.
            </div>
          ) : (
            <div className="flex items-center gap-2.5 overflow-x-auto -mx-1.5 px-1.5 py-2 scrollbar-thin scrollbar-thumb-gray-800">
              {candidateStills.map((still) => {
                const isSelected = selectedStillPath
                  ? still.file_path === selectedStillPath
                  : still.is_selected;

                return (
                  <button
                    key={still.file_path}
                    type="button"
                    onClick={() => handleSelectStill(still)}
                    className={`group relative shrink-0 w-28 sm:w-32 aspect-video rounded-lg overflow-hidden border transition-all text-left ${
                      isSelected
                        ? 'border-brand-500 ring-2 ring-brand-500/50 shadow-md scale-[1.02] z-10'
                        : 'border-gray-800 hover:border-gray-600 opacity-75 hover:opacity-100 z-0'
                    }`}
                    title={`Click to select this frame (${still.width}x${still.height}, rating: ${still.vote_average})`}
                  >
                    <img
                      src={still.thumb_url}
                      alt="Episode frame option"
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />

                    {/* Active Selected Pill */}
                    {isSelected && (
                      <div className="absolute top-1 left-1 bg-emerald-600/95 text-white text-[9px] font-bold px-1.5 py-0.5 rounded shadow flex items-center gap-0.5 backdrop-blur-sm">
                        <Check className="w-2.5 h-2.5" />
                        <span>ACTIVE</span>
                      </div>
                    )}

                    {/* Top Pick Badge */}
                    {!isSelected && still.is_top_pick && (
                      <div className="absolute top-1 left-1 bg-purple-600/90 text-white text-[8px] font-semibold px-1 py-0.5 rounded shadow backdrop-blur-sm">
                        ★ BEST
                      </div>
                    )}

                    {/* Provider Tag */}
                    {still.provider && (
                      <div className={`absolute top-1 right-1 px-1 py-0.5 rounded text-[8px] font-mono font-bold shadow backdrop-blur-sm ${
                        still.provider === 'tvdb'
                          ? 'bg-emerald-800/90 text-emerald-200 border border-emerald-600/40'
                          : 'bg-blue-800/90 text-blue-200 border border-blue-600/40'
                      }`}>
                        {still.provider.toUpperCase()}
                      </div>
                    )}

                    {/* Stats overlay */}
                    <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-1 flex items-center justify-between text-[8px] font-mono text-gray-300">
                      <span>★ {still.vote_average}</span>
                      <span>{still.width}p</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Episode Details Bar with Quick Update Button */}
      {currentEp && (
        <div className="bg-dark-900 border border-gray-800 rounded-xl p-2.5 sm:p-3 text-[11px] sm:text-xs text-gray-400 flex items-center justify-between gap-3 shrink-0 flex-wrap sm:flex-nowrap">
          <div className="flex items-center gap-2 truncate mr-1 min-w-0">
            <span className="truncate">
              Episode: <strong className="text-white">{currentEp.title}</strong>
            </span>
            <span className="text-gray-600 hidden sm:inline">•</span>
            <span className="shrink-0 hidden sm:inline">
              Season <strong className="text-white">{currentEp.season_number}</strong> • Episode{' '}
              <strong className="text-white">{currentEp.episode_number}</strong>
            </span>
          </div>

          {onApplySingleCard && (
            <button
              type="button"
              onClick={onApplySingleCard}
              disabled={isApplyingSingle || isEpisodesLoading}
              className={`font-bold px-3 py-1.5 rounded-lg text-xs transition flex items-center gap-1.5 shadow shrink-0 ${
                testMode && !isForceLive
                  ? 'bg-amber-500 hover:bg-amber-400 text-dark-950'
                  : 'bg-brand-500 hover:bg-brand-400 text-dark-950 shadow-brand-500/20'
              } disabled:opacity-50`}
              title={
                testMode && !isForceLive
                  ? `Simulate title card generation for S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')} (Test Mode)`
                  : `Upload title card for S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')} directly to Plex`
              }
            >
              {isApplyingSingle ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
              ) : testMode && !isForceLive ? (
                <Sparkles className="w-3.5 h-3.5 shrink-0" />
              ) : (
                <Send className="w-3.5 h-3.5 shrink-0" />
              )}
              <span className="whitespace-nowrap">
                {isApplyingSingle
                  ? 'Updating Card...'
                  : testMode && !isForceLive
                  ? `Simulate This Card (S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')})`
                  : `Update This Card (S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')})`}
              </span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};
