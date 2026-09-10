import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Show, Episode, StyleConfig, MediuxSet } from '../types';
import { api } from '../api';
import { useToast } from '../context/ToastContext';
import {
  X,
  Sliders,
  Eye,
  Zap,
  Wand2,
  Ban,
  Sparkles,
  FlaskConical,
  ExternalLink,
  CheckCircle,
  Check,
  RotateCcw,
  Loader2,
  LayoutTemplate,
  Upload,
  Star,
  Search,
  Edit2,
  AlertTriangle,
  RefreshCw,
  Film
} from 'lucide-react';

// Global cache for preview object URLs across modal opens
const previewBlobCache = new Map<string, string>();
// Global cache for show MediUX sets across modal opens
const mediuxSetsCache = new Map<string, MediuxSet[]>();

const normalizeSeparator = (sep?: string): string => {
  if (!sep || sep === 'none') return '';
  if (sep === 'dot' || sep === 'bullet' || sep === 'delta') return '•';
  if (sep === 'dash') return '-';
  return sep;
};

const getSubheadingPreview = (fmt?: string, icon?: string): string => {
  const sep = icon === 'none' ? '' : (icon || '•');
  switch (fmt) {
    case 'season_word_ep_word':
      return `SEASON ONE ${sep ? sep + ' ' : ''}EPISODE FIVE`.trim();
    case 'season_num_ep_num':
      return `SEASON 1 ${sep ? sep + ' ' : ''}EPISODE 5`.trim();
    case 's_pad_e_pad':
      return `S01 ${sep ? sep + ' ' : ''}E05`.trim();
    case 'compact_pad':
      return 'S01E05';
    case 'ep_num':
      return 'EPISODE 5';
    case 'ep_word':
      return 'EPISODE FIVE';
    case 'e_pad':
      return 'E05';
    case 'season_num':
      return 'SEASON 1';
    case 'season_word':
      return 'SEASON ONE';
    default:
      return `SEASON 1 ${sep ? sep + ' ' : ''}EPISODE 5`.trim();
  }
};

interface ShowStudioModalProps {
  show: Show;
  testMode: boolean;
  onClose: () => void;
  onShowUpdated: () => void;
}

export const ShowStudioModal: React.FC<ShowStudioModalProps> = ({
  show,
  testMode,
  onClose,
  onShowUpdated
}) => {
  const [activeShow, setActiveShow] = useState<Show>(show);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [isEpisodesLoading, setIsEpisodesLoading] = useState<boolean>(true);
  const [availableSets, setAvailableSets] = useState<MediuxSet[]>(() => {
    return mediuxSetsCache.get(show.rating_key) || [];
  });
  const [isSetsLoading, setIsSetsLoading] = useState<boolean>(() => {
    return !mediuxSetsCache.has(show.rating_key);
  });
  const [autoMediuxSetId, setAutoMediuxSetId] = useState<string | null>(null);
  const [preferredCreators, setPreferredCreators] = useState<string[]>([]);
  const [selectedEpIndex, setSelectedEpIndex] = useState<number>(0);
  const [previewUrl, setPreviewUrl] = useState<string>('');
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [isApplying, setIsApplying] = useState<boolean>(false);
  const [applyProgress, setApplyProgress] = useState<{ current: number; total: number; label?: string } | null>(null);
  const [isAiLoading, setIsAiLoading] = useState<boolean>(false);
  const [aiPrompt, setAiPrompt] = useState<string>('');
  const [aiReasoning, setAiReasoning] = useState<string>(show.ai_prompt || '');
  const [availableFonts, setAvailableFonts] = useState<{ name: string; type: string; filename: string }[]>([]);
  const [isUploadingFont, setIsUploadingFont] = useState<boolean>(false);
  const [isSavedJustNow, setIsSavedJustNow] = useState<boolean>(false);
  const [updateScope, setUpdateScope] = useState<'all' | 'missing'>('all');
  const [isForceLive, setIsForceLive] = useState<boolean>(false);
  const [previewTab, setPreviewTab] = useState<'mediux' | 'generator'>('mediux');

  // TMDb search and matching state
  const [isTmdbModalOpen, setIsTmdbModalOpen] = useState<boolean>(false);
  const [tmdbSearchQuery, setTmdbSearchQuery] = useState<string>('');
  const [tmdbSearchYear, setTmdbSearchYear] = useState<string>('');
  const [tmdbSearchResults, setTmdbSearchResults] = useState<any[]>([]);
  const [isSearchingTmdb, setIsSearchingTmdb] = useState<boolean>(false);
  const [customTmdbIdInput, setCustomTmdbIdInput] = useState<string>('');
  const [isLinkingTmdb, setIsLinkingTmdb] = useState<boolean>(false);

  // Plex fix match state
  const [isPlexFixMatchConfirmOpen, setIsPlexFixMatchConfirmOpen] = useState<boolean>(false);
  const [isFixingPlexMatch, setIsFixingPlexMatch] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  const [styleConfig, setStyleConfig] = useState<StyleConfig>({
    layout: show.layout || 'standard',
    text_position: (show.text_position as any) || 'left_center',
    font_family: show.font_family || 'Montserrat',
    font_color: show.font_color || '#FFFFFF',
    subheading_color: show.subheading_color || '#A3A3A3',
    gradient_side: show.gradient_side || 'left',
    gradient_width_pct: show.gradient_width_pct || 48,
    gradient_opacity_pct: show.gradient_opacity_pct || 88,
    show_subheading: show.show_subheading !== undefined ? show.show_subheading : 1,
    subheading_format: show.subheading_format || 'season_num_ep_num',
    subheading_icon: normalizeSeparator(show.subheading_icon)
  });

  // Load details, episodes, fonts, and available sets
  useEffect(() => {
    let isMounted = true;
    setIsEpisodesLoading(true);
    if (!mediuxSetsCache.has(show.rating_key)) {
      setIsSetsLoading(true);
    }

    api.getFonts().then((fonts) => {
      if (isMounted) setAvailableFonts(fonts);
    });

    api.getShowDetails(show.rating_key).then((data) => {
      if (!isMounted) return;
      setActiveShow(data.show);
      setEpisodes(data.episodes || []);
      const sets = data.available_sets || [];
      mediuxSetsCache.set(show.rating_key, sets);
      setAvailableSets(sets);
      setAutoMediuxSetId(data.auto_mediux_set_id || null);
      setPreferredCreators(data.preferred_creators || []);
      setIsEpisodesLoading(false);
      setIsSetsLoading(false);

      if (data.ai_error) {
        showToast({
          type: 'warning',
          title: 'Gemini AI Temporarily Unavailable',
          message: data.ai_error
        });
      }

      // If backend auto-suggested a style on first load, apply it to state
      if (data.show) {
        setStyleConfig({
          layout: data.show.layout || 'standard',
          text_position: (data.show.text_position as any) || 'left_center',
          font_family: data.show.font_family || 'Montserrat',
          font_color: data.show.font_color || '#FFFFFF',
          subheading_color: data.show.subheading_color || '#A3A3A3',
          gradient_side: data.show.gradient_side || 'left',
          gradient_width_pct: data.show.gradient_width_pct || 48,
          gradient_opacity_pct: data.show.gradient_opacity_pct || 88,
          show_subheading: data.show.show_subheading !== undefined ? data.show.show_subheading : 1,
          subheading_format: data.show.subheading_format || 'season_num_ep_num',
          subheading_icon: normalizeSeparator(data.show.subheading_icon)
        });
        if (data.show.ai_prompt) {
          setAiReasoning(data.show.ai_prompt);
        }
      }

      if (data.initial_ai_generated) {
        onShowUpdated();
      }
    });
    return () => {
      isMounted = false;
    };
  }, [show.rating_key]);

  const handleFontUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingFont(true);
    try {
      const res = await api.uploadFont(file);
      const updatedFonts = await api.getFonts();
      setAvailableFonts(updatedFonts);
      setStyleConfig((prev) => ({ ...prev, font_family: res.font_name }));
      showToast({
        type: 'success',
        title: 'Font Uploaded',
        message: `Custom font "${res.font_name}" uploaded and selected!`
      });
    } catch (err) {
      showToast({
        type: 'error',
        title: 'Font Upload Failed',
        message: String(err)
      });
    } finally {
      setIsUploadingFont(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Refresh preview with client and server caching
  useEffect(() => {
    if (episodes.length === 0) return;
    const ep = episodes[selectedEpIndex];
    if (!ep) return;

    // Check frontend in-memory cache first for instantaneous rendering
    const cacheKey = `${activeShow.rating_key}_s${ep.season_number}e${ep.episode_number}_${styleConfig.text_position}_${styleConfig.font_family}_${styleConfig.font_color}_${styleConfig.subheading_color}_${styleConfig.show_subheading}_${styleConfig.subheading_format}_${styleConfig.subheading_icon}_${styleConfig.gradient_width_pct}_${styleConfig.gradient_opacity_pct}`;
    if (previewBlobCache.has(cacheKey)) {
      setPreviewUrl(previewBlobCache.get(cacheKey)!);
      setIsPreviewLoading(false);
      return;
    }

    let active = true;
    setIsPreviewLoading(true);

    api
      .getPreviewBlob(activeShow.rating_key, {
        season_number: ep.season_number,
        episode_number: ep.episode_number,
        episode_title: ep.title,
        ...styleConfig
      })
      .then((blob) => {
        if (!active) return;
        const objectUrl = URL.createObjectURL(blob);
        previewBlobCache.set(cacheKey, objectUrl);
        setPreviewUrl(objectUrl);
        setIsPreviewLoading(false);
      })
      .catch((err) => {
        console.error('Preview error:', err);
        if (active) setIsPreviewLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedEpIndex, episodes, styleConfig, activeShow.rating_key]);

  const handleModeChange = async (newMode: 'auto' | 'generator_only' | 'ignored') => {
    setActiveShow((prev) => ({ ...prev, mode: newMode }));
    await api.setMode(activeShow.rating_key, newMode, activeShow.mediux_set_url);
    onShowUpdated();
  };

  const handleSelectSet = async (selectedSet: MediuxSet | null) => {
    const newUrl = selectedSet ? selectedSet.set_url : undefined;
    setActiveShow((prev) => ({ ...prev, mediux_set_url: newUrl }));
    try {
      await api.setMode(activeShow.rating_key, activeShow.mode, newUrl);
      if (selectedSet) {
        showToast({
          type: 'success',
          title: 'MediUX Set Selected',
          message: `Locked to MediUX set by ${selectedSet.creator}`
        });
      } else {
        showToast({
          type: 'info',
          title: 'Reset to Auto',
          message: 'Now using automatic best matching MediUX set'
        });
      }
      onShowUpdated();
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Error',
        message: err.message || 'Failed to update selected set'
      });
    }
  };

  const handleOpenTmdbModal = () => {
    const q = activeShow.title || '';
    const y = activeShow.year ? String(activeShow.year) : '';
    setTmdbSearchQuery(q);
    setTmdbSearchYear(y);
    setCustomTmdbIdInput(activeShow.tmdb_id ? String(activeShow.tmdb_id) : '');
    setTmdbSearchResults([]);
    setIsTmdbModalOpen(true);
    if (q) {
      handleSearchTmdb(q, y);
    }
  };

  const handleSearchTmdb = async (query: string, year?: string) => {
    if (!query.trim()) return;
    setIsSearchingTmdb(true);
    try {
      const yearNum = year && !isNaN(parseInt(year, 10)) ? parseInt(year, 10) : undefined;
      const data = await api.searchTmdb(query.trim(), yearNum);
      setTmdbSearchResults(data.results || []);
    } catch (err) {
      showToast({
        type: 'error',
        title: 'TMDb Search Error',
        message: String(err)
      });
    } finally {
      setIsSearchingTmdb(false);
    }
  };

  const handleLinkTmdb = async (tmdbId: number) => {
    setIsLinkingTmdb(true);
    try {
      await api.setTmdbMatch(activeShow.rating_key, tmdbId);
      showToast({
        type: 'success',
        title: 'TMDb Show Linked',
        message: `Linked "${activeShow.title}" to TMDb ID ${tmdbId}.`
      });
      setIsTmdbModalOpen(false);

      // Refresh show details and MediUX sets
      setIsSetsLoading(true);
      const updated = await api.getShowDetails(activeShow.rating_key);
      setActiveShow(updated.show);
      setEpisodes(updated.episodes || []);
      const sets = updated.available_sets || [];
      mediuxSetsCache.set(activeShow.rating_key, sets);
      setAvailableSets(sets);
      setAutoMediuxSetId(updated.auto_mediux_set_id || null);
      setIsSetsLoading(false);

      onShowUpdated();
    } catch (err) {
      showToast({
        type: 'error',
        title: 'Failed to Link TMDb',
        message: String(err)
      });
    } finally {
      setIsLinkingTmdb(false);
    }
  };

  const handlePlexFixMatch = async () => {
    setIsFixingPlexMatch(true);
    try {
      const res = await api.plexFixMatch(activeShow.rating_key);
      showToast({
        type: 'success',
        title: 'Plex Fix Match Triggered',
        message: res.message || `Successfully requested Plex to fix match "${activeShow.title}".`
      });
      setIsPlexFixMatchConfirmOpen(false);
      onShowUpdated();
    } catch (err) {
      showToast({
        type: 'error',
        title: 'Plex Fix Match Failed',
        message: String(err)
      });
    } finally {
      setIsFixingPlexMatch(false);
    }
  };

  const handleTogglePreferredCreator = async (creatorName: string) => {
    const isPref = preferredCreators.some(
      (c) => c.toLowerCase() === creatorName.toLowerCase()
    );
    let updated: string[];
    if (isPref) {
      updated = preferredCreators.filter(
        (c) => c.toLowerCase() !== creatorName.toLowerCase()
      );
    } else {
      updated = [...preferredCreators, creatorName];
    }
    setPreferredCreators(updated);

    try {
      await api.updateSettings({
        preferred_mediux_creators: updated.join(', ')
      });
      showToast({
        type: 'success',
        title: isPref ? 'Creator Preference Removed' : 'Creator Set as Preferred',
        message: isPref
          ? `Removed "${creatorName}" from preferred creators.`
          : `Added "${creatorName}" to preferred creators. Sets by ${creatorName} will now be prioritized in Auto mode.`
      });

      // If in auto mode without manual override, re-evaluate auto-selection
      if (!activeShow.mediux_set_url && availableSets.length > 0) {
        const cleanPrefs = updated.map((c) => c.trim().toLowerCase());
        const prefSet = availableSets.find((s) =>
          cleanPrefs.includes((s.creator || '').trim().toLowerCase())
        );
        if (prefSet) {
          setAutoMediuxSetId(prefSet.id);
        } else if (availableSets[0]) {
          setAutoMediuxSetId(availableSets[0].id);
        }
      }
    } catch (err) {
      showToast({
        type: 'error',
        title: 'Save Failed',
        message: String(err)
      });
    }
  };

  const applyPreset = (preset: 'cinematic' | 'clean_bottom') => {
    if (preset === 'cinematic') {
      setStyleConfig((prev) => ({
        ...prev,
        text_position: 'left_bottom',
        font_family: 'Bebas Neue',
        font_color: '#FFFFFF',
        subheading_color: '#CCCCCC',
        subheading_icon: '•',
        gradient_side: 'bottom',
        gradient_width_pct: 50
      }));
    } else if (preset === 'clean_bottom') {
      setStyleConfig((prev) => ({
        ...prev,
        text_position: 'center_bottom',
        font_family: 'Montserrat',
        font_color: '#FFFFFF',
        subheading_color: '#A3A3A3',
        subheading_icon: '-',
        gradient_side: 'bottom',
        gradient_width_pct: 45
      }));
    }
  };

  const handleAiSuggest = async () => {
    setIsAiLoading(true);
    setAiReasoning('');
    try {
      const suggestion = await api.askAi(activeShow.rating_key, aiPrompt);
      if (suggestion.font_family) {
        setStyleConfig((prev) => ({
          ...prev,
          font_family: suggestion.font_family,
          font_color: suggestion.font_color || prev.font_color,
          subheading_color: suggestion.subheading_color || prev.subheading_color,
          subheading_icon: suggestion.subheading_icon || prev.subheading_icon,
          text_position: suggestion.text_position || prev.text_position,
          gradient_side: suggestion.gradient_side || prev.gradient_side,
          gradient_width_pct: suggestion.gradient_width_pct || prev.gradient_width_pct
        }));
      }
      setAiReasoning(suggestion.reasoning || '');
      showToast({
        type: 'success',
        title: 'Style Suggested',
        message: `Gemini recommended "${suggestion.font_family}" typography.`
      });
    } catch (err: any) {
      const msg = err?.message || String(err);
      showToast({
        type: 'error',
        title: 'Gemini AI Error',
        message: msg
      });
      setAiReasoning(`❌ ${msg}`);
    } finally {
      setIsAiLoading(false);
    }
  };

  const handleSaveStyle = async () => {
    try {
      await api.saveStyle(activeShow.rating_key, {
        ...styleConfig,
        ai_prompt: aiReasoning
      });
      setIsSavedJustNow(true);
      setTimeout(() => setIsSavedJustNow(false), 2500);
      showToast({
        type: 'success',
        title: 'Preset Saved',
        message: `Title card style preset saved for "${activeShow.title}".`
      });
      onShowUpdated();
    } catch (err) {
      showToast({
        type: 'error',
        title: 'Save Failed',
        message: String(err)
      });
    }
  };

  const handleApply = async () => {
    setIsApplying(true);
    setApplyProgress(null);
    try {
      // 1. Auto-save current styling first so preview matches what gets generated
      await api.saveStyle(activeShow.rating_key, {
        ...styleConfig,
        ai_prompt: aiReasoning
      });

      // 2. Apply cards with selected scope and mode, tracking progress
      const res = await api.applyCards(
        activeShow.rating_key,
        {
          force_all: updateScope === 'all',
          force_live: isForceLive
        },
        (progress) => {
          setApplyProgress(progress);
        }
      );

      const posterNote = res.updated_season_posters ? ` and ${res.updated_season_posters} season posters` : '';
      if (res.test_mode) {
        showToast({
          type: 'info',
          title: '🧪 Test Mode Simulation',
          message: `Rendered ${res.updated_cards} cards${posterNote} locally to cache/test_output/. Check 'Push Live to Plex' to upload.`
        });
      } else {
        showToast({
          type: 'success',
          title: 'Plex Updated',
          message: `Successfully updated ${res.updated_cards} episode cards${posterNote} in Plex!`
        });
      }
      onShowUpdated();
    } catch (e) {
      showToast({
        type: 'error',
        title: 'Update Failed',
        message: String(e)
      });
    } finally {
      setIsApplying(false);
      setApplyProgress(null);
    }
  };

  const currentEp = episodes[selectedEpIndex];

  // Determine which set ID is currently selected (manual choice or auto-pick)
  const selectedSetId = activeShow.mediux_set_url
    ? availableSets.find(
        (s) =>
          s.set_url === activeShow.mediux_set_url ||
          (s.id && activeShow.mediux_set_url?.includes(s.id))
      )?.id
    : (autoMediuxSetId || (availableSets.length > 0 ? availableSets[0].id : null));

  // Sort sets: The active selected set is ALWAYS at the top (index 0),
  // followed by sets from preferred creators, then total card count descending.
  const sortedSets = useMemo(() => {
    if (!availableSets || availableSets.length <= 1) return availableSets;

    return [...availableSets].sort((a, b) => {
      const aIsSelected = a.id === selectedSetId;
      const bIsSelected = b.id === selectedSetId;
      if (aIsSelected && !bIsSelected) return -1;
      if (!aIsSelected && bIsSelected) return 1;

      const aIsPref = preferredCreators.some(
        (c) => c.toLowerCase() === (a.creator || '').toLowerCase()
      );
      const bIsPref = preferredCreators.some(
        (c) => c.toLowerCase() === (b.creator || '').toLowerCase()
      );
      if (aIsPref && !bIsPref) return -1;
      if (!aIsPref && bIsPref) return 1;

      return (b.total_cards || 0) - (a.total_cards || 0);
    });
  }, [availableSets, selectedSetId, preferredCreators]);

  // Active MediUX set (for preview and rendering)
  const activeMediuxSet =
    activeShow.mode === 'auto' && sortedSets.length > 0
      ? sortedSets.find((s) => s.id === selectedSetId) || sortedSets[0]
      : null;

  // Title card from active MediUX set for this episode
  const currentEpMediuxCardUrl =
    activeMediuxSet && currentEp
      ? activeMediuxSet.title_cards?.[`${currentEp.season_number}_${currentEp.episode_number}`]
      : null;

  const isShowingMediux = Boolean(
    activeShow.mode === 'auto' &&
    currentEpMediuxCardUrl &&
    previewTab === 'mediux'
  );

  const activeDisplayUrl = isShowingMediux ? currentEpMediuxCardUrl : previewUrl;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-dark-900 border border-gray-800 rounded-xl sm:rounded-2xl w-full max-w-6xl h-[96vh] sm:h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-3 sm:px-6 py-2.5 sm:py-4 border-b border-gray-800 bg-dark-850 flex flex-col md:flex-row md:items-center justify-between gap-2.5 sm:gap-3 shrink-0">
          <div className="flex items-start md:items-center justify-between gap-3 min-w-0">
            <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-brand-500/20 text-brand-500 flex items-center justify-center font-bold shrink-0">
                <Sliders className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <h2 className="text-base sm:text-lg font-bold text-white truncate">
                  {activeShow.title}
                </h2>
                <div className="flex items-center gap-1.5 sm:gap-2 text-[11px] sm:text-xs text-gray-400 mt-0.5 flex-wrap">
                  {activeShow.year && <span>{activeShow.year}</span>}
                  {activeShow.year && <span>•</span>}
                  {activeShow.tmdb_id ? (
                    <div className="flex items-center gap-1 bg-dark-800 border border-gray-700/80 px-1.5 py-0.5 rounded text-[10px] sm:text-[11px]">
                      <a
                        href={`https://www.themoviedb.org/tv/${activeShow.tmdb_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-300 hover:text-brand-400 flex items-center gap-1 transition"
                        title="View show on TMDb"
                      >
                        <span>TMDb: {activeShow.tmdb_id}</span>
                        <ExternalLink className="w-2.5 h-2.5 text-gray-500" />
                      </a>
                      <button
                        type="button"
                        onClick={handleOpenTmdbModal}
                        className="text-gray-400 hover:text-white transition p-0.5 hover:bg-dark-700 rounded ml-0.5"
                        title="Edit or Change TMDb Match"
                      >
                        <Edit2 className="w-2.5 h-2.5" />
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={handleOpenTmdbModal}
                      className="inline-flex items-center gap-1 text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 px-2 py-0.5 rounded text-[10px] sm:text-[11px] font-semibold transition"
                      title="Find and link this show to TMDb"
                    >
                      <AlertTriangle className="w-3 h-3" />
                      Link TMDb
                    </button>
                  )}

                  <span className="text-gray-600 hidden xs:inline">•</span>
                  <button
                    type="button"
                    onClick={() => setIsPlexFixMatchConfirmOpen(true)}
                    className="text-gray-400 hover:text-blue-400 transition text-[10px] sm:text-[11px] flex items-center gap-1 bg-dark-800 hover:bg-dark-700 border border-gray-700/80 px-1.5 py-0.5 rounded"
                    title="Prompt Plex to fix match this show with the Plex Series Agent"
                  >
                    <RefreshCw className="w-2.5 h-2.5" />
                    <span className="hidden sm:inline">Fix Match in Plex</span>
                    <span className="sm:hidden">Fix Match</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Mobile Close X Button */}
            <button
              type="button"
              onClick={onClose}
              className="md:hidden text-gray-400 hover:text-white p-1 rounded-lg transition shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Header Action Controls */}
          <div className="flex items-center flex-wrap md:flex-nowrap gap-2 justify-between md:justify-end">
            {/* Scope Toggle: All vs Missing */}
            <div className="flex items-center bg-dark-800 border border-gray-700 rounded-lg p-0.5 text-xs shrink-0">
              <button
                type="button"
                onClick={() => setUpdateScope('all')}
                className={`px-2 sm:px-2.5 py-1 rounded-md text-[11px] sm:text-xs font-medium transition ${
                  updateScope === 'all'
                    ? 'bg-brand-500 text-dark-950 font-bold shadow-sm'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
                title="Update and overwrite cards for all episodes"
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setUpdateScope('missing')}
                className={`px-2 sm:px-2.5 py-1 rounded-md text-[11px] sm:text-xs font-medium transition ${
                  updateScope === 'missing'
                    ? 'bg-brand-500 text-dark-950 font-bold shadow-sm'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
                title="Only generate/download cards for episodes that are missing title cards"
              >
                Missing Only
              </button>
            </div>

            {/* If TEST_MODE is active, allow user to toggle Force Live */}
            {testMode && (
              <label className="flex items-center gap-1 text-[11px] sm:text-xs text-amber-400 cursor-pointer bg-amber-500/10 border border-amber-500/30 px-2 py-1 rounded-lg hover:bg-amber-500/15 transition select-none shrink-0">
                <input
                  type="checkbox"
                  checked={isForceLive}
                  onChange={(e) => setIsForceLive(e.target.checked)}
                  className="rounded text-amber-500 focus:ring-0 cursor-pointer"
                />
                <span className="font-semibold text-[10px] sm:text-[11px]">Live to Plex</span>
              </label>
            )}

            {/* Apply / Update Button with Dynamic Progress */}
            <div className="flex-1 md:flex-none flex flex-col gap-1 min-w-[120px] sm:min-w-[170px]">
              <button
                type="button"
                onClick={handleApply}
                disabled={isApplying}
                className={`${
                  testMode && !isForceLive
                    ? 'bg-amber-500 hover:bg-amber-600 text-dark-950'
                    : 'bg-brand-500 hover:bg-brand-600 text-dark-950'
                } disabled:opacity-50 font-bold px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs flex items-center justify-center gap-1.5 transition shadow-md w-full`}
              >
                {isApplying ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                ) : testMode && !isForceLive ? (
                  <FlaskConical className="w-3.5 h-3.5 shrink-0" />
                ) : (
                  <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                )}
                <span className="truncate">
                  {isApplying
                    ? applyProgress && applyProgress.total > 0
                      ? `${testMode && !isForceLive ? 'Sim' : 'Updating'} ${applyProgress.current}/${applyProgress.total}`
                      : 'Updating...'
                    : testMode && !isForceLive
                    ? `Simulate (${updateScope === 'all' ? 'All' : 'Missing'})`
                    : `Update Plex (${updateScope === 'all' ? 'All' : 'Missing'})`}
                </span>
              </button>

              {/* Progress bar */}
              {isApplying && applyProgress && applyProgress.total > 0 && (
                <div className="w-full bg-dark-800 rounded-full h-1 overflow-hidden">
                  <div
                    className={`${testMode && !isForceLive ? 'bg-amber-400' : 'bg-brand-400'} h-full transition-all duration-200 rounded-full`}
                    style={{
                      width: `${Math.min(100, Math.round((applyProgress.current / applyProgress.total) * 100))}%`
                    }}
                  />
                </div>
              )}
            </div>

            {/* Desktop close button */}
            <button
              type="button"
              onClick={onClose}
              className="hidden md:block text-gray-400 hover:text-white p-2 rounded-lg transition shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto lg:overflow-hidden grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-gray-800">
          {/* Left: Preview Canvas (7 cols) */}
          <div className="lg:col-span-7 p-3 sm:p-5 lg:p-6 flex flex-col gap-3 sm:gap-4 bg-dark-950/40 lg:overflow-y-auto">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                  <Eye className="w-4 h-4 text-brand-500" /> Live Preview
                </span>

                {/* View Switcher: MediUX Card vs Generator Fallback */}
                {currentEpMediuxCardUrl && activeShow.mode === 'auto' && (
                  <div className="flex items-center bg-dark-800 p-0.5 rounded-lg border border-gray-700 text-[11px]">
                    <button
                      type="button"
                      onClick={() => setPreviewTab('mediux')}
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
                      onClick={() => setPreviewTab('generator')}
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
                    onChange={(e) => setSelectedEpIndex(Number(e.target.value))}
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

            {/* Preview Frame: Constrained on mobile/tablet, full on desktop */}
            <div className="w-full flex justify-center">
              <div className="relative aspect-video w-full max-w-[340px] sm:max-w-[460px] lg:max-w-none bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl flex items-center justify-center">
                {activeDisplayUrl ? (
                  <img
                    src={activeDisplayUrl}
                    alt="Title Card Preview"
                    className="w-full h-full object-cover"
                  />
                ) : isEpisodesLoading && !activeShow.has_custom_style ? (
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
                        Analyzing {activeShow.title}'s genres & tone while TMDb downloads 1080p backdrop stills.
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
                    <span>
                      MediUX Card • {activeMediuxSet?.creator}
                    </span>
                  </div>
                )}

                {activeDisplayUrl && !isShowingMediux && currentEpMediuxCardUrl && activeShow.mode === 'auto' && (
                  <div className="absolute top-2 sm:top-3 left-2 sm:left-3 bg-dark-950/85 backdrop-blur-md px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full border border-purple-500/50 text-purple-300 text-[10px] sm:text-[11px] font-medium flex items-center gap-1 sm:gap-1.5 shadow">
                    <Wand2 className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-purple-400" />
                    <span>Generator Preview (Fallback)</span>
                  </div>
                )}

                {activeDisplayUrl && activeShow.mode === 'auto' && !currentEpMediuxCardUrl && (
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
              </div>
            </div>

            {currentEp && (
              <div className="bg-dark-900 border border-gray-800 rounded-xl p-2.5 sm:p-3 text-[11px] sm:text-xs text-gray-400 flex items-center justify-between">
                <span className="truncate mr-2">
                  Episode: <strong className="text-white">{currentEp.title}</strong>
                </span>
                <span className="shrink-0">
                  Season <strong className="text-white">{currentEp.season_number}</strong> • Episode{' '}
                  <strong className="text-white">{currentEp.episode_number}</strong>
                </span>
              </div>
            )}
          </div>

          {/* Right: Controls & Studio (5 cols) */}
          <div className="lg:col-span-5 p-4 sm:p-6 flex flex-col gap-5 sm:gap-6 bg-dark-900 lg:overflow-y-auto">
            {/* Mode Switcher */}
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-gray-400 block mb-2">
                Card Source Mode
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => handleModeChange('auto')}
                  className={`border rounded-lg p-2 text-center text-xs font-medium transition ${
                    activeShow.mode === 'auto'
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                      : 'bg-dark-800 border-gray-700 text-gray-400'
                  }`}
                >
                  <Zap className="w-4 h-4 mx-auto mb-1" />
                  Auto (MediUX)
                </button>

                <button
                  type="button"
                  onClick={() => handleModeChange('generator_only')}
                  className={`border rounded-lg p-2 text-center text-xs font-medium transition ${
                    activeShow.mode === 'generator_only'
                      ? 'bg-purple-500/20 border-purple-500 text-purple-300'
                      : 'bg-dark-800 border-gray-700 text-gray-400'
                  }`}
                >
                  <Wand2 className="w-4 h-4 mx-auto mb-1" />
                  Generator Only
                </button>

                <button
                  type="button"
                  onClick={() => handleModeChange('ignored')}
                  className={`border rounded-lg p-2 text-center text-xs font-medium transition ${
                    activeShow.mode === 'ignored'
                      ? 'bg-gray-700 border-gray-500 text-white'
                      : 'bg-dark-800 border-gray-700 text-gray-400'
                  }`}
                >
                  <Ban className="w-4 h-4 mx-auto mb-1" />
                  Ignored
                </button>
              </div>

              {activeShow.mode === 'auto' && (
                <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">
                  Checks MediUX for sets that cover all your seasons. Automatically fills missing or newly aired episodes with the generator and updates once uploaded.
                </p>
              )}
              {activeShow.mode === 'generator_only' && (
                <p className="text-[11px] text-purple-400/90 mt-2 leading-relaxed">
                  Never polls MediUX. Automatically creates cards for every episode using the style preset below.
                </p>
              )}
            </div>

            {/* MediUX Sets (when in Auto mode) */}
            {activeShow.mode === 'auto' && (
              <div className="border-t border-gray-800 pt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-2">
                    <span>Detected MediUX Sets</span>
                    {!isSetsLoading && (
                      <span className="text-gray-500 font-normal">({sortedSets.length})</span>
                    )}
                    {isSetsLoading && (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-500 inline" />
                    )}
                  </label>
                  {!isSetsLoading && activeShow.mediux_set_url && (
                    <button
                      type="button"
                      onClick={() => handleSelectSet(null)}
                      className="text-[11px] text-amber-400 hover:text-amber-300 hover:underline flex items-center gap-1 font-medium transition"
                    >
                      <RotateCcw className="w-3 h-3" /> Reset to Auto-Pick
                    </button>
                  )}
                </div>

                {isSetsLoading ? (
                  <div className="py-7 flex flex-col items-center justify-center gap-2.5 text-gray-400 bg-dark-850/50 border border-gray-800 rounded-xl">
                    <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
                    <span className="text-xs text-gray-400">Checking MediUX for title cards and season posters...</span>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {sortedSets.map((set, idx) => {
                      const isManual = Boolean(
                        activeShow.mediux_set_url &&
                        (activeShow.mediux_set_url === set.set_url ||
                         (set.id && activeShow.mediux_set_url.includes(set.id)))
                      );
                      const isAutoDefault = !activeShow.mediux_set_url && set.id === selectedSetId;
                      const isSelected = isManual || isAutoDefault;
                      const isPreferred = preferredCreators.some(
                        (c) => c.toLowerCase() === (set.creator || '').toLowerCase()
                      );

                      return (
                        <div
                          key={set.id}
                          className={`rounded-lg p-2.5 flex items-center justify-between text-xs transition border ${
                            isSelected
                              ? isManual
                                ? 'bg-purple-950/30 border-purple-500/60 ring-1 ring-purple-500/40'
                                : 'bg-emerald-950/30 border-emerald-500/60 ring-1 ring-emerald-500/40'
                              : 'bg-dark-850 border-gray-800 hover:border-gray-700'
                          }`}
                        >
                          <div className="flex-1 mr-3">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-semibold text-white">{set.creator}</span>
                              {isManual && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-500/20 text-purple-300 border border-purple-500/40">
                                  Chosen by You
                                </span>
                              )}
                              {isAutoDefault && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                                  Auto-Selected
                                </span>
                              )}
                              {isPreferred ? (
                                <button
                                  type="button"
                                  title={`Preferred creator: ${set.creator}. Click to remove preference.`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleTogglePreferredCreator(set.creator);
                                  }}
                                  className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 flex items-center gap-1 transition"
                                >
                                  <Star className="w-2.5 h-2.5 fill-amber-400 text-amber-400" /> Preferred
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  title={`Add ${set.creator} to preferred creators`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleTogglePreferredCreator(set.creator);
                                  }}
                                  className="px-1.5 py-0.5 rounded text-[10px] text-gray-400 hover:text-amber-300 border border-gray-700/60 hover:border-amber-500/50 hover:bg-amber-500/10 flex items-center gap-1 transition"
                                >
                                  <Star className="w-2.5 h-2.5" /> + Prefer
                                </button>
                              )}
                            </div>
                            <span className="text-gray-500 text-[11px] block mt-0.5">
                              {set.total_cards} cards • Seasons: {set.seasons_covered.join(', ')}
                              {set.season_posters && Object.keys(set.season_posters).length > 0 && (
                                <span className="text-brand-400 font-medium ml-1.5">
                                  • {Object.keys(set.season_posters).length} season {Object.keys(set.season_posters).length === 1 ? 'poster' : 'posters'}
                                </span>
                              )}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {isSelected ? (
                              <span className={`text-[11px] font-medium flex items-center gap-1 ${
                                isManual ? 'text-purple-400' : 'text-emerald-400'
                              }`}>
                                <Check className="w-3.5 h-3.5" /> Active
                              </span>
                            ) : (
                              <button
                                type="button"
                                onClick={() => handleSelectSet(set)}
                                className="px-2 py-1 rounded text-[11px] font-medium bg-dark-750 hover:bg-dark-700 text-gray-200 border border-gray-700 hover:border-gray-600 transition"
                              >
                                Use This Set
                              </button>
                            )}
                            <a
                              href={set.set_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-brand-500 hover:underline text-[11px] flex items-center gap-1 ml-1"
                            >
                              View <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </div>
                      );
                    })}
                    {sortedSets.length === 0 && (
                      <div className="text-xs text-gray-500 italic p-1">
                        No sets with title cards detected on MediUX. Generator fallback will be used!
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Generator Studio */}
            <div className="border-t border-gray-800 pt-4 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Generator Styling
                </label>
                <div className="flex items-center gap-1 text-[11px]">
                  <button
                    onClick={() => applyPreset('cinematic')}
                    className="px-2 py-0.5 rounded bg-gray-800 text-gray-300 hover:bg-gray-700"
                  >
                    Cinematic
                  </button>
                  <button
                    onClick={() => applyPreset('clean_bottom')}
                    className="px-2 py-0.5 rounded bg-gray-800 text-gray-300 hover:bg-gray-700"
                  >
                    Bottom Center
                  </button>
                </div>
              </div>

              {/* AI Assistant */}
              <div className="bg-dark-850 border border-purple-500/30 rounded-xl p-3 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-purple-300 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" /> AI Style Assistant
                  </span>
                  <span className="text-[10px] text-gray-500">Gemini 3.6 Flash</span>
                </div>
                {isEpisodesLoading && !activeShow.has_custom_style ? (
                  <div className="bg-purple-950/40 border border-purple-500/30 rounded-lg p-2.5 flex items-center gap-2 text-xs text-purple-300 animate-pulse">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400 shrink-0" />
                    <span>Gemini is analyzing show tone to recommend initial styling...</span>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="e.g., Gritty thriller with bold white font..."
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAiSuggest()}
                      className="flex-1 bg-dark-900 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
                    />
                    <button
                      onClick={handleAiSuggest}
                      disabled={isAiLoading}
                      className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
                    >
                      {isAiLoading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Sparkles className="w-3.5 h-3.5" />
                      )}
                      <span>Suggest</span>
                    </button>
                  </div>
                )}
                {aiReasoning && (
                  <p className="text-[11px] text-gray-400 italic mt-1 leading-relaxed">
                    {aiReasoning}
                  </p>
                )}
              </div>

              {/* Request 3: Text Positioning */}
              <div>
                <label className="text-[11px] text-gray-400 block mb-1">Text Position</label>
                <select
                  value={styleConfig.text_position}
                  onChange={(e) => {
                    const pos = e.target.value as any;
                    const grad = pos.includes('bottom') ? 'bottom' : pos.includes('right') ? 'right' : 'left';
                    setStyleConfig((prev) => ({
                      ...prev,
                      text_position: pos,
                      gradient_side: grad
                    }));
                  }}
                  className="w-full bg-dark-800 border border-gray-700 text-xs rounded-lg px-3 py-2 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="left_center">Left Middle</option>
                  <option value="left_bottom">Bottom Left</option>
                  <option value="center_bottom">Bottom Center</option>
                  <option value="right_center">Right Middle</option>
                  <option value="right_bottom">Bottom Right</option>
                </select>
              </div>

              {/* Font Family & Custom Font Upload */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[11px] text-gray-400">Font Family</label>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploadingFont}
                    className="text-[11px] text-brand-400 hover:text-brand-300 flex items-center gap-1 transition"
                  >
                    {isUploadingFont ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Upload className="w-3 h-3" />
                    )}
                    <span>Upload Font (.ttf / .otf)</span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".ttf,.otf"
                    onChange={handleFontUpload}
                    className="hidden"
                  />
                </div>
                <select
                  value={styleConfig.font_family}
                  onChange={(e) =>
                    setStyleConfig((prev) => ({ ...prev, font_family: e.target.value }))
                  }
                  className="w-full bg-dark-800 border border-gray-700 text-xs rounded-lg px-3 py-2 text-white focus:outline-none focus:border-brand-500"
                >
                  {/* If current font isn't in list (e.g. newly suggested by AI), render it dynamically */}
                  {styleConfig.font_family &&
                    !availableFonts.some(
                      (f) => f.name.toLowerCase() === styleConfig.font_family?.toLowerCase()
                    ) && (
                      <option value={styleConfig.font_family}>
                        {styleConfig.font_family} (Auto-downloaded / AI suggested)
                      </option>
                    )}
                  {availableFonts.map((f) => (
                    <option key={f.name} value={f.name}>
                      {f.name} {f.type === 'custom' ? '★ (Custom Upload)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Title Font Color */}
              <div>
                <label className="text-[11px] text-gray-400 block mb-1">Title Font Color</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={styleConfig.font_color}
                    onChange={(e) =>
                      setStyleConfig((prev) => ({ ...prev, font_color: e.target.value }))
                    }
                    className="w-8 h-8 rounded border border-gray-700 bg-transparent cursor-pointer"
                  />
                  <input
                    type="text"
                    value={styleConfig.font_color}
                    onChange={(e) =>
                      setStyleConfig((prev) => ({ ...prev, font_color: e.target.value }))
                    }
                    className="w-full bg-dark-800 border border-gray-700 text-xs rounded px-2 py-1.5 text-white font-mono uppercase"
                  />
                </div>
              </div>

              {/* Subheading Options Card */}
              <div className="bg-dark-850/60 border border-gray-800 rounded-xl p-3 space-y-3">
                {/* Header + Visibility Toggle */}
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-xs font-semibold text-white block">Subheading</label>
                    <span className="text-[10px] text-gray-400">Season & episode label above title</span>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      setStyleConfig((prev) => ({
                        ...prev,
                        show_subheading: prev.show_subheading ? 0 : 1
                      }))
                    }
                    className={`text-xs px-2.5 py-1 rounded-full border font-medium transition flex items-center gap-1.5 ${
                      styleConfig.show_subheading
                        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        : 'bg-dark-800 text-gray-400 border-gray-700 hover:text-white'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${styleConfig.show_subheading ? 'bg-emerald-400' : 'bg-gray-500'}`} />
                    <span>{styleConfig.show_subheading ? 'Visible' : 'Hidden'}</span>
                  </button>
                </div>

                {styleConfig.show_subheading ? (
                  <>
                    {/* Live Subheading Preview Badge */}
                    <div className="bg-dark-950/80 border border-gray-800 rounded-lg py-1.5 px-3 flex items-center justify-between text-xs">
                      <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Preview</span>
                      <span
                        className="font-mono font-bold tracking-wide"
                        style={{ color: styleConfig.subheading_color }}
                      >
                        {getSubheadingPreview(styleConfig.subheading_format, styleConfig.subheading_icon)}
                      </span>
                    </div>

                    {/* Subheading Format Selector */}
                    <div>
                      <label className="text-[11px] text-gray-400 block mb-1">
                        Format Style
                      </label>
                      <select
                        value={styleConfig.subheading_format}
                        onChange={(e) =>
                          setStyleConfig((prev) => ({
                            ...prev,
                            subheading_format: e.target.value
                          }))
                        }
                        className="w-full bg-dark-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-brand-500 font-medium"
                      >
                        <option value="season_num_ep_num">Season 1 • Episode 1 (Standard)</option>
                        <option value="s_pad_e_pad">S01 • E01 (Short Code)</option>
                        <option value="season_word_ep_word">Season One • Episode One (Words)</option>
                        <option value="compact_pad">S01E01 (Compact)</option>
                        <option value="ep_num">Episode 1 (Episode Only - No Season)</option>
                        <option value="ep_word">Episode One (Episode Only - No Season)</option>
                        <option value="e_pad">E01 (Episode Code Only - No Season)</option>
                        <option value="season_num">Season 1 (Season Only)</option>
                      </select>

                      {/* Quick Format Chips */}
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {[
                          { id: 'season_num_ep_num', label: 'Season 1 • Ep 1' },
                          { id: 's_pad_e_pad', label: 'S01 • E01' },
                          { id: 'ep_num', label: 'Episode 1' },
                          { id: 'e_pad', label: 'E01' },
                          { id: 'season_word_ep_word', label: 'Words' },
                          { id: 'compact_pad', label: 'S01E01' }
                        ].map((chip) => {
                          const isSelected = styleConfig.subheading_format === chip.id;
                          return (
                            <button
                              key={chip.id}
                              type="button"
                              onClick={() =>
                                setStyleConfig((prev) => ({
                                  ...prev,
                                  subheading_format: chip.id
                                }))
                              }
                              className={`text-[10px] px-2 py-0.5 rounded border transition font-medium ${
                                isSelected
                                  ? 'bg-brand-500/20 text-brand-400 border-brand-500/40'
                                  : 'bg-dark-800 text-gray-400 border-gray-700 hover:text-white hover:bg-dark-750'
                              }`}
                            >
                              {chip.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Separator - only show when both season and episode are visible */}
                    {!['ep_num', 'ep_word', 'e_pad', 'season_num', 'season_word', 's_pad', 'compact_pad'].includes(styleConfig.subheading_format) && (
                      <div>
                        <label className="text-[11px] text-gray-400 block mb-1.5">
                          Separator Character
                        </label>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            maxLength={4}
                            value={styleConfig.subheading_icon}
                            onChange={(e) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                subheading_icon: e.target.value
                              }))
                            }
                            placeholder="None"
                            className="w-14 bg-dark-800 border border-gray-700 text-xs rounded-lg px-2 py-1.5 text-white font-mono text-center focus:outline-none focus:border-brand-500"
                            title="Type any custom separator character"
                          />
                          <div className="flex flex-wrap items-center gap-1 flex-1">
                            {[
                              { label: '•', val: '•' },
                              { label: ':', val: ':' },
                              { label: '-', val: '-' },
                              { label: '=', val: '=' },
                              { label: '|', val: '|' },
                              { label: '.', val: '.' },
                              { label: '/', val: '/' },
                              { label: '~', val: '~' },
                              { label: 'None', val: '' }
                            ].map((item) => {
                              const isSelected = styleConfig.subheading_icon === item.val;
                              return (
                                <button
                                  key={item.label}
                                  type="button"
                                  onClick={() =>
                                    setStyleConfig((prev) => ({
                                      ...prev,
                                      subheading_icon: item.val
                                    }))
                                  }
                                  className={`px-2 py-0.5 text-xs rounded border transition font-medium ${
                                    isSelected
                                      ? 'bg-brand-600 border-brand-500 text-white shadow-sm'
                                      : 'bg-dark-800 border-gray-700 text-gray-400 hover:text-white hover:bg-dark-750'
                                  }`}
                                >
                                  {item.label}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Subheading Color */}
                    <div>
                      <label className="text-[11px] text-gray-400 block mb-1">Subheading Color</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={styleConfig.subheading_color}
                          onChange={(e) =>
                            setStyleConfig((prev) => ({
                              ...prev,
                              subheading_color: e.target.value
                            }))
                          }
                          className="w-8 h-8 rounded border border-gray-700 bg-transparent cursor-pointer"
                        />
                        <input
                          type="text"
                          value={styleConfig.subheading_color}
                          onChange={(e) =>
                            setStyleConfig((prev) => ({
                              ...prev,
                              subheading_color: e.target.value
                            }))
                          }
                          className="w-full bg-dark-800 border border-gray-700 text-xs rounded px-2 py-1.5 text-white font-mono uppercase"
                        />
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="text-[11px] text-gray-500 italic">
                    Subheading is hidden. Cards will be rendered with episode title only.
                  </p>
                )}
              </div>

              {/* Gradient Sliders */}
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-[11px] text-gray-400 mb-1">
                    <span>Gradient Width / Height</span>
                    <span>{styleConfig.gradient_width_pct}%</span>
                  </div>
                  <input
                    type="range"
                    min="30"
                    max="65"
                    value={styleConfig.gradient_width_pct}
                    onChange={(e) =>
                      setStyleConfig((prev) => ({
                        ...prev,
                        gradient_width_pct: Number(e.target.value)
                      }))
                    }
                    className="w-full accent-brand-500 bg-dark-800"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-[11px] text-gray-400 mb-1">
                    <span>Gradient Opacity</span>
                    <span>{styleConfig.gradient_opacity_pct}%</span>
                  </div>
                  <input
                    type="range"
                    min="60"
                    max="100"
                    value={styleConfig.gradient_opacity_pct}
                    onChange={(e) =>
                      setStyleConfig((prev) => ({
                        ...prev,
                        gradient_opacity_pct: Number(e.target.value)
                      }))
                    }
                    className="w-full accent-brand-500 bg-dark-800"
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={handleSaveStyle}
                disabled={isSavedJustNow}
                className={`w-full font-semibold py-2 rounded-lg text-xs transition flex items-center justify-center gap-1.5 mt-2 ${
                  isSavedJustNow
                    ? 'bg-emerald-600/25 text-emerald-300 border border-emerald-500/50'
                    : 'bg-dark-800 hover:bg-dark-700 border border-gray-700 text-white'
                }`}
              >
                {isSavedJustNow ? (
                  <>
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Preset Saved!</span>
                  </>
                ) : (
                  <span>Save Style Preset</span>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* TMDb Search & Link Modal */}
      {isTmdbModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-dark-900 border border-gray-700 w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between bg-dark-850">
              <div>
                <h3 className="font-bold text-white text-sm flex items-center gap-2">
                  <Film className="w-4 h-4 text-brand-500" />
                  Link TMDb TV Show
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Search TMDb to match &ldquo;{activeShow.title}&rdquo; or enter a numeric ID directly.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsTmdbModalOpen(false)}
                className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-dark-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 border-b border-gray-800 space-y-3 bg-dark-850/50">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSearchTmdb(tmdbSearchQuery, tmdbSearchYear);
                }}
                className="flex gap-2"
              >
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={tmdbSearchQuery}
                    onChange={(e) => setTmdbSearchQuery(e.target.value)}
                    placeholder="Search TV show title..."
                    className="w-full bg-dark-950 border border-gray-700 text-white rounded-lg pl-9 pr-3 py-1.5 text-xs focus:border-brand-500 focus:outline-none"
                  />
                </div>
                <input
                  type="text"
                  value={tmdbSearchYear}
                  onChange={(e) => setTmdbSearchYear(e.target.value)}
                  placeholder="Year (opt)"
                  className="w-20 bg-dark-950 border border-gray-700 text-white rounded-lg px-2.5 py-1.5 text-xs focus:border-brand-500 focus:outline-none text-center"
                />
                <button
                  type="submit"
                  disabled={isSearchingTmdb || !tmdbSearchQuery.trim()}
                  className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition shrink-0"
                >
                  {isSearchingTmdb ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                  Search
                </button>
              </form>

              <div className="flex items-center gap-2 pt-1 border-t border-gray-800/80">
                <span className="text-[11px] text-gray-400 shrink-0">Direct TMDb ID:</span>
                <input
                  type="number"
                  value={customTmdbIdInput}
                  onChange={(e) => setCustomTmdbIdInput(e.target.value)}
                  placeholder="e.g. 95442"
                  className="w-32 bg-dark-950 border border-gray-700 text-white rounded-lg px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => {
                    const idNum = parseInt(customTmdbIdInput, 10);
                    if (idNum) handleLinkTmdb(idNum);
                  }}
                  disabled={isLinkingTmdb || !customTmdbIdInput.trim()}
                  className="bg-dark-800 hover:bg-dark-700 text-gray-200 border border-gray-700 px-2.5 py-1 rounded-lg text-xs font-medium disabled:opacity-50 transition"
                >
                  Link ID
                </button>
              </div>
            </div>

            {/* Search Results List */}
            <div className="p-4 overflow-y-auto flex-1 space-y-2.5 min-h-[220px]">
              {isSearchingTmdb ? (
                <div className="flex flex-col items-center justify-center py-10 text-gray-400 gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
                  <p className="text-xs">Searching TMDb database...</p>
                </div>
              ) : tmdbSearchResults.length > 0 ? (
                tmdbSearchResults.map((res) => (
                  <div
                    key={res.tmdb_id}
                    className="flex items-center justify-between p-3 rounded-xl bg-dark-800/70 border border-gray-700/80 hover:border-brand-500/50 transition gap-3"
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="w-12 h-16 bg-dark-950 rounded-lg overflow-hidden shrink-0 border border-gray-800">
                        {res.poster_url ? (
                          <img
                            src={res.poster_url}
                            alt={res.name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-600 text-[10px]">
                            No Art
                          </div>
                        )}
                      </div>
                      <div className="overflow-hidden">
                        <div className="flex items-center gap-2">
                          <h4 className="font-bold text-white text-xs truncate">
                            {res.name}
                          </h4>
                          {res.year && (
                            <span className="text-[11px] text-gray-400 bg-dark-900 px-1.5 py-0.5 rounded border border-gray-800">
                              {res.year}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-gray-400 line-clamp-2 mt-0.5">
                          {res.overview || 'No overview available.'}
                        </p>
                        <p className="text-[10px] text-gray-500 mt-0.5">
                          TMDb ID: {res.tmdb_id}
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleLinkTmdb(res.tmdb_id)}
                      disabled={isLinkingTmdb}
                      className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-bold px-3 py-1.5 rounded-lg text-xs shrink-0 transition"
                    >
                      {activeShow.tmdb_id === res.tmdb_id ? 'Active Match' : 'Select & Link'}
                    </button>
                  </div>
                ))
              ) : (
                <div className="text-center py-10 text-gray-500 text-xs">
                  {tmdbSearchQuery ? 'No TV shows found matching this search.' : 'Type a query above to search TMDb.'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Plex Fix Match Confirmation Dialog */}
      {isPlexFixMatchConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-dark-900 border border-gray-700 w-full max-w-md rounded-2xl shadow-2xl p-5 space-y-4">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-blue-500/10 border border-blue-500/30 rounded-xl text-blue-400 shrink-0">
                <RefreshCw className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-white text-sm">
                  Fix Match in Plex?
                </h3>
                <p className="text-xs text-gray-300 mt-1 leading-relaxed">
                  This will instruct Plex Media Server to search its agent for <strong className="text-white">&ldquo;{activeShow.title}&rdquo;</strong> and apply official metadata (description, cast, genres).
                </p>
                <p className="text-[11px] text-amber-400/90 mt-2 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20 leading-tight">
                  ⚠️ <strong>Note:</strong> When Plex matches a show, Plex may download its own default artwork. If needed, you can re-apply your custom cards and posters here at any time.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-2 border-t border-gray-800">
              <button
                type="button"
                onClick={() => setIsPlexFixMatchConfirmOpen(false)}
                disabled={isFixingPlexMatch}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white hover:bg-dark-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePlexFixMatch}
                disabled={isFixingPlexMatch}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold px-4 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition shadow-md"
              >
                {isFixingPlexMatch ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Fixing in Plex...</span>
                  </>
                ) : (
                  <span>Yes, Fix Match in Plex</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
