import React, { useState, useEffect, useMemo } from 'react';
import { Show, Episode, MediuxSet, StyleConfig } from '../types';
import { api } from '../api';
import { useToast } from '../context/ToastContext';
import { StudioHeader } from './studio/StudioHeader';
import { StudioPreviewCanvas } from './studio/StudioPreviewCanvas';
import { MediuxSetBrowser } from './studio/MediuxSetBrowser';
import { GeneratorControls } from './studio/GeneratorControls';
import { TmdbLinkModal } from './studio/TmdbLinkModal';
import { PlexFixMatchModal } from './studio/PlexFixMatchModal';

// Keep a component-level cache of downloaded preview ObjectURLs so cycling episodes or toggling tabs is instant
const previewBlobCache = new Map<string, string>();
// In-memory cache for MediUX sets per show to avoid redundant fetches
const mediuxSetsCache = new Map<string, MediuxSet[]>();

const normalizeSeparator = (icon?: string): string => {
  if (icon === 'bullet' || icon === '•' || icon === undefined || icon === null) return '•';
  if (icon === 'dash' || icon === '-') return '-';
  if (icon === 'pipe' || icon === '|') return '|';
  if (icon === 'slash' || icon === '/') return '/';
  if (icon === 'none' || icon === '') return '';
  return icon;
};

interface ShowStudioModalProps {
  show: Show;
  testMode: boolean;
  hasGeminiKey?: boolean;
  onClose: () => void;
  onShowUpdated: () => void;
}

export const ShowStudioModal: React.FC<ShowStudioModalProps> = ({
  show,
  testMode,
  hasGeminiKey: initialHasGeminiKey = true,
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
  const [updateScope, setUpdateScope] = useState<'all' | 'missing' | 'current'>('all');
  const [isApplyingSingle, setIsApplyingSingle] = useState<boolean>(false);
  const [isForceLive, setIsForceLive] = useState<boolean>(false);
  const [previewTab, setPreviewTab] = useState<'mediux' | 'generator'>('mediux');
  const [hasGeminiKey, setHasGeminiKey] = useState<boolean>(initialHasGeminiKey);
  const [isExportingZip, setIsExportingZip] = useState<boolean>(false);

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

  const { showToast } = useToast();
  const [stillNonce, setStillNonce] = useState<number>(0);

  const [styleConfig, setStyleConfig] = useState<StyleConfig>({
    layout: show.layout || 'standard',
    text_position: (show.text_position as any) || 'left_center',
    font_family: show.font_family || 'Oswald',
    subheading_font_family: show.subheading_font_family || undefined,
    font_color: show.font_color || '#FFFFFF',
    subheading_color: show.subheading_color || '#A3A3A3',
    gradient_side: show.gradient_side || 'left',
    gradient_width_pct: show.gradient_width_pct || 48,
    gradient_opacity_pct: show.gradient_opacity_pct || 88,
    show_subheading: show.show_subheading !== undefined ? show.show_subheading : 1,
    subheading_format: show.subheading_format || 'season_num_ep_num',
    subheading_icon: normalizeSeparator(show.subheading_icon),
    title_font_size: show.title_font_size || 108,
    subheading_font_size: show.subheading_font_size || 52,
    text_box_width_pct: show.text_box_width_pct || 46,
    subheading_gap: show.subheading_gap !== undefined ? show.subheading_gap : 16,
    subheading_casing: show.subheading_casing || 'upper',
    subheading_position: show.subheading_position || 'above',
    subheading_tracking: show.subheading_tracking !== undefined ? show.subheading_tracking : 0,
    frosted_blur_pct: show.frosted_blur_pct !== undefined ? show.frosted_blur_pct : 0,
    film_grain_pct: show.film_grain_pct !== undefined ? show.film_grain_pct : 0,
    vignette_pct: show.vignette_pct !== undefined ? show.vignette_pct : 0,
    text_shadow_mode: show.text_shadow_mode || 'none',
    show_logo: show.show_logo !== undefined ? show.show_logo : 0,
    logo_position: show.logo_position || 'top_right',
    logo_opacity_pct: show.logo_opacity_pct !== undefined ? show.logo_opacity_pct : 90,
    logo_monochrome: show.logo_monochrome !== undefined ? show.logo_monochrome : 0
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

      if (data.has_gemini_key !== undefined) {
        setHasGeminiKey(Boolean(data.has_gemini_key));
      }

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
          font_family: data.show.font_family || 'Oswald',
          subheading_font_family: data.show.subheading_font_family || undefined,
          font_color: data.show.font_color || '#FFFFFF',
          subheading_color: data.show.subheading_color || '#A3A3A3',
          gradient_side: data.show.gradient_side || 'left',
          gradient_width_pct: data.show.gradient_width_pct || 48,
          gradient_opacity_pct: data.show.gradient_opacity_pct || 88,
          show_subheading: data.show.show_subheading !== undefined ? data.show.show_subheading : 1,
          subheading_format: data.show.subheading_format || 'season_num_ep_num',
          subheading_icon: normalizeSeparator(data.show.subheading_icon),
          title_font_size: data.show.title_font_size || 108,
          subheading_font_size: data.show.subheading_font_size || 52,
          text_box_width_pct: data.show.text_box_width_pct || 46,
          subheading_gap: data.show.subheading_gap !== undefined ? data.show.subheading_gap : 16,
          subheading_casing: data.show.subheading_casing || 'upper',
          subheading_position: data.show.subheading_position || 'above',
          subheading_tracking: data.show.subheading_tracking !== undefined ? data.show.subheading_tracking : 0,
          frosted_blur_pct: data.show.frosted_blur_pct !== undefined ? data.show.frosted_blur_pct : 0,
          film_grain_pct: data.show.film_grain_pct !== undefined ? data.show.film_grain_pct : 0,
          vignette_pct: data.show.vignette_pct !== undefined ? data.show.vignette_pct : 0,
          text_shadow_mode: data.show.text_shadow_mode || 'none',
          show_logo: data.show.show_logo !== undefined ? data.show.show_logo : 0,
          logo_position: data.show.logo_position || 'top_right',
          logo_opacity_pct: data.show.logo_opacity_pct !== undefined ? data.show.logo_opacity_pct : 90,
          logo_monochrome: data.show.logo_monochrome !== undefined ? data.show.logo_monochrome : 0
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

  // Refresh preview with client and server caching
  useEffect(() => {
    if (episodes.length === 0) return;
    const ep = episodes[selectedEpIndex];
    if (!ep) return;

    const cacheKey = `${activeShow.rating_key}_s${ep.season_number}e${ep.episode_number}_${styleConfig.text_position}_${styleConfig.font_family}_${styleConfig.subheading_font_family || ''}_${styleConfig.font_color}_${styleConfig.subheading_color}_${styleConfig.show_subheading}_${styleConfig.subheading_format}_${styleConfig.subheading_icon}_${styleConfig.gradient_width_pct}_${styleConfig.gradient_opacity_pct}_${styleConfig.title_font_size}_${styleConfig.subheading_font_size}_${styleConfig.text_box_width_pct || 46}_${styleConfig.subheading_gap !== undefined ? styleConfig.subheading_gap : 16}_${styleConfig.subheading_casing || 'upper'}_${styleConfig.subheading_position || 'above'}_${styleConfig.subheading_tracking || 0}_${styleConfig.frosted_blur_pct || 0}_${styleConfig.film_grain_pct || 0}_${styleConfig.vignette_pct || 0}_${styleConfig.text_shadow_mode || 'none'}_${styleConfig.show_logo || 0}_${styleConfig.logo_position || 'top_right'}_${styleConfig.logo_opacity_pct || 90}_${styleConfig.logo_monochrome || 0}_${stillNonce}`;
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
        ...styleConfig,
        subheading_font_family: styleConfig.subheading_font_family || ''
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
  }, [selectedEpIndex, episodes, styleConfig, activeShow.rating_key, stillNonce]);

  const handleModeChange = async (newMode: 'auto' | 'generator_only' | 'ignored') => {
    setActiveShow((prev) => ({ ...prev, mode: newMode }));
    await api.setMode(activeShow.rating_key, newMode, activeShow.mediux_set_url);
    onShowUpdated();
  };

  const handleSelectSet = async (selectedSet: MediuxSet | null) => {
    const newUrl = selectedSet ? selectedSet.set_url : undefined;
    const newMode = activeShow.mode === 'ignored' ? 'auto' : activeShow.mode;
    setActiveShow((prev) => ({ ...prev, mediux_set_url: newUrl, mode: newMode }));
    try {
      await api.setMode(activeShow.rating_key, newMode, newUrl);
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
        gradient_width_pct: 50,
        title_font_size: 115,
        subheading_font_size: 54
      }));
    } else if (preset === 'clean_bottom') {
      setStyleConfig((prev) => ({
        ...prev,
        text_position: 'center_bottom',
        font_family: 'Oswald',
        font_color: '#FFFFFF',
        subheading_color: '#A3A3A3',
        subheading_icon: '-',
        gradient_side: 'bottom',
        gradient_width_pct: 48,
        title_font_size: 106,
        subheading_font_size: 50,
        text_box_width_pct: 55
      }));
    }
  };

  const handleAiSuggest = async () => {
    setIsAiLoading(true);
    setAiReasoning('');
    try {
      const effectivePrompt = aiPrompt.trim();
      const currentEp = episodes[selectedEpIndex];
      const suggestion = await api.askAi(
        activeShow.rating_key,
        effectivePrompt,
        currentEp?.season_number,
        currentEp?.episode_number
      );
      if (suggestion.font_family) {
        setStyleConfig((prev) => ({
          ...prev,
          font_family: suggestion.font_family,
          subheading_font_family: suggestion.subheading_font_family || undefined,
          font_color: suggestion.font_color || prev.font_color,
          subheading_color: suggestion.subheading_color || prev.subheading_color,
          subheading_icon: suggestion.subheading_icon || prev.subheading_icon,
          text_position: suggestion.text_position || prev.text_position,
          gradient_side: suggestion.gradient_side || prev.gradient_side,
          gradient_width_pct: suggestion.gradient_width_pct || prev.gradient_width_pct,
          gradient_opacity_pct: suggestion.gradient_opacity_pct || prev.gradient_opacity_pct,
          title_font_size: suggestion.title_font_size || prev.title_font_size || 108,
          subheading_font_size: suggestion.subheading_font_size || prev.subheading_font_size || 52,
          subheading_position: suggestion.subheading_position || prev.subheading_position,
          subheading_casing: suggestion.subheading_casing || prev.subheading_casing,
          subheading_tracking: suggestion.subheading_tracking !== undefined ? suggestion.subheading_tracking : prev.subheading_tracking,
          subheading_format: suggestion.subheading_format || prev.subheading_format,
          subheading_gap: suggestion.subheading_gap !== undefined ? suggestion.subheading_gap : prev.subheading_gap,
          text_box_width_pct: suggestion.text_box_width_pct || prev.text_box_width_pct,
          frosted_blur_pct: suggestion.frosted_blur_pct !== undefined ? suggestion.frosted_blur_pct : prev.frosted_blur_pct,
          film_grain_pct: suggestion.film_grain_pct !== undefined ? suggestion.film_grain_pct : prev.film_grain_pct,
          vignette_pct: suggestion.vignette_pct !== undefined ? suggestion.vignette_pct : prev.vignette_pct,
          text_shadow_mode: suggestion.text_shadow_mode || prev.text_shadow_mode,
          show_logo: suggestion.show_logo !== undefined ? suggestion.show_logo : prev.show_logo,
          logo_position: suggestion.logo_position || prev.logo_position,
          logo_opacity_pct: suggestion.logo_opacity_pct !== undefined ? suggestion.logo_opacity_pct : prev.logo_opacity_pct,
          logo_monochrome: suggestion.logo_monochrome !== undefined ? suggestion.logo_monochrome : prev.logo_monochrome
        }));
      }
      setAiReasoning(suggestion.reasoning || '');

      const fontSummary = suggestion.subheading_font_family && suggestion.subheading_font_family !== suggestion.font_family
        ? `• Fonts: "${suggestion.font_family}" & "${suggestion.subheading_font_family}"`
        : `• Font: "${suggestion.font_family}"`;

      const posFormatted = (suggestion.text_position || 'left_center').replace(/_/g, ' ');
      const subPos = suggestion.subheading_position ? ` (${suggestion.subheading_position} title)` : '';
      const layoutSummary = `• Layout: ${posFormatted.charAt(0).toUpperCase() + posFormatted.slice(1)}${subPos}`;

      const colorSummary = `• Colors: ${suggestion.font_color || '#FFFFFF'} (Title) / ${suggestion.subheading_color || '#A3A3A3'} (Sub)`;
      const sizeSummary = `• Sizes: ${suggestion.title_font_size || 108}px Title / ${suggestion.subheading_font_size || 52}px Sub`;

      const casingLabel = suggestion.subheading_casing === 'upper' ? 'UPPER' : suggestion.subheading_casing === 'title' ? 'Title Case' : 'lower';
      const trackingLabel = suggestion.subheading_tracking ? `+${suggestion.subheading_tracking}px tracking` : 'no tracking';
      const subDetail = `• Subtitle: ${casingLabel}, ${trackingLabel}`;

      const fxParts: string[] = [];
      if (suggestion.frosted_blur_pct) fxParts.push(`${suggestion.frosted_blur_pct}% Frosted Blur`);
      if (suggestion.film_grain_pct) fxParts.push(`${suggestion.film_grain_pct}% Grain`);
      if (suggestion.vignette_pct) fxParts.push(`${suggestion.vignette_pct}% Vignette`);
      if (suggestion.text_shadow_mode && suggestion.text_shadow_mode !== 'none') fxParts.push(`${suggestion.text_shadow_mode} shadow`);
      const fxSummary = fxParts.length > 0 ? `• Cinematic FX: ${fxParts.join(', ')}` : '';

      const fullSummary = [fontSummary, colorSummary, layoutSummary, sizeSummary, subDetail, fxSummary].filter(Boolean).join('\n');

      showToast({
        type: 'success',
        title: 'Gemini Style Recommendation Applied',
        message: fullSummary,
        duration: 6000
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
      if (e.target) e.target.value = '';
    }
  };

  const handleSaveStyle = async () => {
    try {
      await api.saveStyle(activeShow.rating_key, {
        ...styleConfig,
        subheading_font_family: styleConfig.subheading_font_family || '',
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

  const currentEp = episodes[selectedEpIndex];

  const handleApplySingle = async () => {
    if (!currentEp) return;
    setIsApplyingSingle(true);
    try {
      // 1. Auto-save current styling first so preview matches what gets generated
      await api.saveStyle(activeShow.rating_key, {
        ...styleConfig,
        subheading_font_family: styleConfig.subheading_font_family || '',
        ai_prompt: aiReasoning
      });

      // 2. Apply single episode card
      const res = await api.applyEpisodeCard(
        activeShow.rating_key,
        currentEp.season_number,
        currentEp.episode_number,
        {
          force_live: isForceLive,
          source: isShowingMediux ? 'mediux' : 'generator',
          custom_style: styleConfig
        }
      );

      const epLabel = `S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')}`;
      if (res.test_mode) {
        showToast({
          type: 'info',
          title: '🧪 Test Mode Simulation',
          message: `Rendered ${epLabel} locally to cache/test_output/. Check 'Live Upload' to push to Plex.`
        });
      } else {
        showToast({
          type: 'success',
          title: 'Plex Card Updated',
          message: `Successfully updated ${epLabel} in Plex!`
        });
      }

      // If show was ignored and this is live upload, promote to active mode
      if (activeShow.mode === 'ignored' && isForceLive) {
        const newMode = isShowingMediux ? 'auto' : 'generator_only';
        setActiveShow((prev) => ({ ...prev, mode: newMode }));
        await api.setMode(activeShow.rating_key, newMode, activeShow.mediux_set_url);
      }

      // Update local episode in state
      setEpisodes((prev) =>
        prev.map((ep) =>
          ep.rating_key === currentEp.rating_key
            ? { ...ep, card_source: res.source }
            : ep
        )
      );

      onShowUpdated();
    } catch (e: any) {
      showToast({
        type: 'error',
        title: 'Update Failed',
        message: e.message || String(e)
      });
    } finally {
      setIsApplyingSingle(false);
    }
  };

  const handleApply = async () => {
    if (updateScope === 'current') {
      await handleApplySingle();
      return;
    }

    setIsApplying(true);
    setApplyProgress(null);
    try {
      // 1. Auto-save current styling first so preview matches what gets generated
      await api.saveStyle(activeShow.rating_key, {
        ...styleConfig,
        subheading_font_family: styleConfig.subheading_font_family || '',
        ai_prompt: aiReasoning
      });

      // If show was currently set to ignored, promote it to active mode
      let currentMode = activeShow.mode;
      if (currentMode === 'ignored') {
        currentMode = (selectedSetId || activeShow.mediux_set_url || availableSets.length > 0)
          ? 'auto'
          : 'generator_only';
        setActiveShow((prev) => ({ ...prev, mode: currentMode }));
        await api.setMode(activeShow.rating_key, currentMode, activeShow.mediux_set_url);
      }

      // 2. Apply cards with selected scope and mode, tracking progress
      const res = await api.applyCards(
        activeShow.rating_key,
        {
          force_all: updateScope === 'all',
          force_live: isForceLive,
          source_mode: currentMode
        },
        (progress) => {
          setApplyProgress(progress);
        }
      );

      if (res.status === 'skipped') {
        showToast({
          type: 'warning',
          title: 'Show Skipped',
          message: res.message || 'Show is set to ignored. Switch mode to Auto or Generator to update cards.'
        });
        return;
      }

      const count = typeof res.updated_cards === 'number' ? res.updated_cards : 0;
      const posterNote = res.updated_season_posters ? ` and ${res.updated_season_posters} season posters` : '';
      if (res.test_mode) {
        showToast({
          type: 'info',
          title: '🧪 Test Mode Simulation',
          message: `Rendered ${count} cards${posterNote} locally to cache/test_output/. Check 'Live Upload' to push to Plex.`
        });
      } else {
        showToast({
          type: 'success',
          title: 'Plex Updated',
          message: `Successfully updated ${count} episode cards${posterNote} in Plex!`
        });
      }
      onShowUpdated();
    } catch (e: any) {
      showToast({
        type: 'error',
        title: 'Update Failed',
        message: e.message || String(e)
      });
    } finally {
      setIsApplying(false);
      setApplyProgress(null);
    }
  };

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
      : undefined;

  const isShowingMediux = Boolean(
    activeShow.mode === 'auto' &&
    currentEpMediuxCardUrl &&
    previewTab === 'mediux'
  );

  const handleExportZip = async () => {
    setIsExportingZip(true);
    try {
      showToast({
        type: 'info',
        title: 'Packaging Title Cards',
        message: `Rendering and packaging 1080p cards for "${activeShow.title}" into a .zip archive...`
      });

      const sourceMode = previewTab === 'mediux' ? 'mediux' : (activeShow.mode === 'generator_only' ? 'generator' : 'auto');
      const blob = await api.downloadShowCardsZip(activeShow.rating_key, sourceMode);

      // Trigger browser file download
      const cleanName = activeShow.title.replace(/[\\/*?:"<>|]/g, '').trim();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${cleanName}_Title_Cards.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      showToast({
        type: 'success',
        title: 'Download Ready',
        message: `Saved "${cleanName}_Title_Cards.zip" successfully!`
      });
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Export Failed',
        message: String(err?.message || err)
      });
    } finally {
      setIsExportingZip(false);
    }
  };

  const activeDisplayUrl = isShowingMediux ? (currentEpMediuxCardUrl || null) : (previewUrl || null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-dark-900 border-0 sm:border border-gray-800 rounded-none sm:rounded-2xl w-full max-w-6xl h-[100dvh] sm:h-[88vh] max-h-[100dvh] sm:max-h-[88vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <StudioHeader
          show={activeShow}
          currentEp={currentEp}
          onClose={onClose}
          onOpenTmdbModal={handleOpenTmdbModal}
          onOpenFixMatchModal={() => setIsPlexFixMatchConfirmOpen(true)}
          updateScope={updateScope}
          onToggleScope={setUpdateScope}
          testMode={testMode}
          isForceLive={isForceLive}
          onToggleForceLive={setIsForceLive}
          isApplying={isApplying || isApplyingSingle}
          applyProgress={applyProgress}
          onApplyCards={handleApply}
          onExportZip={handleExportZip}
          isExportingZip={isExportingZip}
        />

        {/* Modal Body: Responsive flex stack on mobile, 2 columns on desktop */}
        <div className="flex flex-col lg:grid lg:grid-cols-12 flex-1 min-h-0 overflow-y-auto lg:overflow-hidden divide-y lg:divide-y-0 lg:divide-x divide-gray-800">
          {/* Left Column: Live Preview & Episode Picker */}
          <StudioPreviewCanvas
            show={activeShow}
            episodes={episodes}
            selectedEpIndex={selectedEpIndex}
            onSelectEpIndex={setSelectedEpIndex}
            isEpisodesLoading={isEpisodesLoading}
            activeDisplayUrl={activeDisplayUrl}
            previewTab={previewTab}
            onSetPreviewTab={setPreviewTab}
            currentEpMediuxCardUrl={currentEpMediuxCardUrl}
            isShowingMediux={isShowingMediux}
            activeMediuxSet={activeMediuxSet}
            isPreviewLoading={isPreviewLoading}
            previewUrl={previewUrl}
            currentEp={currentEp}
            hasGeminiKey={hasGeminiKey}
            onStillChanged={() => {
              setPreviewTab('generator');
              setStillNonce((n) => n + 1);
            }}
            onApplySingleCard={handleApplySingle}
            isApplyingSingle={isApplyingSingle}
            testMode={testMode}
            isForceLive={isForceLive}
          />

          {/* Right Column: Source Modes, MediUX Sets & Generator Styling */}
          <div className="w-full lg:col-span-5 p-3 sm:p-5 lg:p-6 flex flex-col gap-5 shrink-0 lg:shrink lg:overflow-y-auto min-h-0">
            {/* Source Mode & MediUX Browser */}
            <MediuxSetBrowser
              mode={activeShow.mode}
              onModeChange={handleModeChange}
              isSetsLoading={isSetsLoading}
              sortedSets={sortedSets}
              activeMediuxSetUrl={activeShow.mediux_set_url}
              selectedSetId={selectedSetId}
              preferredCreators={preferredCreators}
              onSelectSet={handleSelectSet}
              onTogglePreferredCreator={handleTogglePreferredCreator}
            />

            {/* Generator Controls */}
            <GeneratorControls
              styleConfig={styleConfig}
              setStyleConfig={setStyleConfig}
              applyPreset={applyPreset}
              aiPrompt={aiPrompt}
              setAiPrompt={setAiPrompt}
              handleAiSuggest={handleAiSuggest}
              isAiLoading={isAiLoading}
              aiReasoning={aiReasoning}
              isEpisodesLoading={isEpisodesLoading}
              activeShowHasCustomStyle={Boolean(activeShow.has_custom_style)}
              availableFonts={availableFonts}
              isUploadingFont={isUploadingFont}
              handleFontUpload={handleFontUpload}
              handleSaveStyle={handleSaveStyle}
              isSavedJustNow={isSavedJustNow}
              hasGeminiKey={hasGeminiKey}
              activeShowRatingKey={activeShow.rating_key}
              currentEp={currentEp}
            />
          </div>
        </div>
      </div>

      {/* TMDb Search & Link Modal */}
      <TmdbLinkModal
        isOpen={isTmdbModalOpen}
        onClose={() => setIsTmdbModalOpen(false)}
        activeShowTitle={activeShow.title}
        activeShowTmdbId={activeShow.tmdb_id}
        tmdbSearchQuery={tmdbSearchQuery}
        setTmdbSearchQuery={setTmdbSearchQuery}
        tmdbSearchYear={tmdbSearchYear}
        setTmdbSearchYear={setTmdbSearchYear}
        handleSearchTmdb={handleSearchTmdb}
        isSearchingTmdb={isSearchingTmdb}
        customTmdbIdInput={customTmdbIdInput}
        setCustomTmdbIdInput={setCustomTmdbIdInput}
        handleLinkTmdb={handleLinkTmdb}
        isLinkingTmdb={isLinkingTmdb}
        tmdbSearchResults={tmdbSearchResults}
      />

      {/* Plex Fix Match Confirmation Dialog */}
      <PlexFixMatchModal
        isOpen={isPlexFixMatchConfirmOpen}
        onClose={() => setIsPlexFixMatchConfirmOpen(false)}
        activeShowTitle={activeShow.title}
        handlePlexFixMatch={handlePlexFixMatch}
        isFixingPlexMatch={isFixingPlexMatch}
      />
    </div>
  );
};
