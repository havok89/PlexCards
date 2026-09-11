import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import { StyleConfig, Show, Episode } from '../types';
import { useToast } from '../context/ToastContext';
import { GeneratorControls } from './studio/GeneratorControls';
import {
  Sliders,
  X,
  Loader2,
  CheckCircle2,
  Tv,
  RotateCcw,
  Sparkles,
  Info
} from 'lucide-react';

interface DefaultStyleModalProps {
  onClose: () => void;
  onSaved?: () => void;
}

const SYSTEM_BASELINE_STYLE: StyleConfig = {
  layout: 'standard',
  text_position: 'left_center',
  font_family: 'Oswald',
  subheading_font_family: '',
  font_color: '#FFFFFF',
  subheading_color: '#A3A3A3',
  gradient_side: 'left',
  gradient_width_pct: 48,
  gradient_opacity_pct: 88,
  show_subheading: 1,
  subheading_format: 's_pad_ep_num',
  subheading_icon: 'dot',
  title_font_size: 108,
  subheading_font_size: 52,
  text_box_width_pct: 46,
  subheading_gap: 16,
  subheading_casing: 'upper',
  subheading_position: 'above',
  subheading_tracking: 0,
  frosted_blur_pct: 0,
  film_grain_pct: 0,
  vignette_pct: 0,
  text_shadow_mode: 'subtle',
  show_logo: 0,
  logo_position: 'top_right',
  logo_opacity_pct: 80,
  logo_monochrome: 1
};

export const DefaultStyleModal: React.FC<DefaultStyleModalProps> = ({
  onClose,
  onSaved
}) => {
  const { showToast } = useToast();
  const [styleConfig, setStyleConfig] = useState<StyleConfig>(SYSTEM_BASELINE_STYLE);
  const [sampleShow, setSampleShow] = useState<Show | null>(null);
  const [sampleEpisode, setSampleEpisode] = useState<Episode | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isSavedJustNow, setIsSavedJustNow] = useState<boolean>(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const [availableFonts, setAvailableFonts] = useState<Array<{ name: string; type: string }>>([]);
  const [isUploadingFont, setIsUploadingFont] = useState<boolean>(false);

  // Load saved default style and first show in library
  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.getDefaultStyle(),
      api.getFonts()
    ])
      .then(([styleRes, fonts]) => {
        if (!mounted) return;
        if (styleRes.style) {
          setStyleConfig({
            ...SYSTEM_BASELINE_STYLE,
            ...styleRes.style
          });
        }
        if (styleRes.sample_show) {
          setSampleShow(styleRes.sample_show);
        }
        if (styleRes.sample_episode) {
          setSampleEpisode(styleRes.sample_episode as any);
        }
        setAvailableFonts(fonts);
      })
      .catch((err) => {
        console.error('Failed to load default style:', err);
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  // Fetch live preview whenever style changes
  useEffect(() => {
    if (isLoading) return;

    let active = true;
    setIsPreviewLoading(true);

    const ratingKey = sampleShow ? sampleShow.rating_key : 'default';
    const sNum = sampleEpisode?.season_number || 1;
    const eNum = sampleEpisode?.episode_number || 1;
    const epTitle = sampleEpisode?.title || 'Sample Episode Title';

    api
      .getPreviewBlob(ratingKey, {
        season_number: sNum,
        episode_number: eNum,
        episode_title: epTitle,
        ...styleConfig,
        subheading_font_family: styleConfig.subheading_font_family || ''
      })
      .then((blob) => {
        if (!active) return;
        const objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
        setIsPreviewLoading(false);
      })
      .catch((err) => {
        console.error('Failed to generate preview for default style:', err);
        if (active) setIsPreviewLoading(false);
      });

    return () => {
      active = false;
    };
  }, [styleConfig, sampleShow?.rating_key, sampleEpisode, isLoading]);

  const handleFontUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingFont(true);
    try {
      const res = await api.uploadFont(file);
      showToast({
        type: 'success',
        title: 'Font Uploaded',
        message: `Font "${res.font_name}" has been installed!`
      });
      const fonts = await api.getFonts();
      setAvailableFonts(fonts);
      setStyleConfig((prev) => ({ ...prev, font_family: res.font_name }));
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Font Upload Failed',
        message: err.message || 'Could not upload font file.'
      });
    } finally {
      setIsUploadingFont(false);
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

  const handleResetToBaseline = () => {
    setStyleConfig(SYSTEM_BASELINE_STYLE);
    showToast({
      type: 'info',
      title: 'Reset to System Default',
      message: 'Restored baseline Oswald / Left Center styling.'
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await api.saveDefaultStyle(styleConfig);
      setIsSavedJustNow(true);
      showToast({
        type: 'success',
        title: 'Default Style Saved',
        message: 'Newly scanned shows will now inherit this default styling!'
      });
      onSaved?.();
      setTimeout(() => setIsSavedJustNow(false), 2500);
    } catch (err: any) {
      showToast({
        type: 'error',
        title: 'Save Failed',
        message: String(err?.message || err)
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-dark-900 border-0 sm:border border-gray-800 rounded-none sm:rounded-2xl w-full max-w-6xl h-[100dvh] sm:h-[88vh] max-h-[100dvh] sm:max-h-[88vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-4 sm:px-6 py-3.5 sm:py-4 border-b border-gray-800 flex items-center justify-between bg-dark-850 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-500/20 text-brand-400 flex items-center justify-center font-bold">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-bold text-white">Default Title Card Style</h2>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/30 font-medium">
                  Universal Template
                </span>
              </div>
              <p className="text-[11px] sm:text-xs text-gray-400">
                Applied automatically to newly discovered shows and fallback interim cards
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-2 rounded-lg transition"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body (2 Columns) */}
        <div className="flex flex-col lg:grid lg:grid-cols-12 flex-1 min-h-0 overflow-y-auto lg:overflow-hidden divide-y lg:divide-y-0 lg:divide-x divide-gray-800">
          {/* Left Column: Live Preview */}
          <div className="w-full lg:col-span-7 p-3 sm:p-5 flex flex-col gap-4 shrink-0 lg:shrink min-h-0 lg:overflow-y-auto bg-dark-950/40">
            {/* Show Backdrop Indicator */}
            <div className="flex items-center justify-between gap-2 px-1">
              <div className="flex items-center gap-2 text-xs text-gray-300">
                <Tv className="w-4 h-4 text-brand-400" />
                <span className="font-semibold">
                  {sampleShow ? `Sample Show: ${sampleShow.title}` : 'Sample Canvas'}
                </span>
                {sampleEpisode && (
                  <span className="text-gray-500 font-mono text-[11px]">
                    (S{String(sampleEpisode.season_number).padStart(2, '0')}E{String(sampleEpisode.episode_number).padStart(2, '0')}: {sampleEpisode.title})
                  </span>
                )}
              </div>
              <span className="text-[10px] font-mono text-gray-500 uppercase tracking-wider">
                1920×1080 Preview
              </span>
            </div>

            {/* Canvas Box */}
            <div className="w-full aspect-video rounded-xl overflow-hidden border border-gray-800 relative shadow-2xl bg-black flex items-center justify-center">
              {isPreviewLoading && (
                <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center z-10">
                  <div className="flex items-center gap-2 bg-dark-900/90 px-3 py-1.5 rounded-lg border border-gray-800 text-xs text-brand-400 shadow-xl">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Rendering preview...</span>
                  </div>
                </div>
              )}

              {previewUrl ? (
                <img
                  src={previewUrl}
                  alt="Default Style Preview"
                  className="w-full h-full object-cover select-none"
                />
              ) : (
                <div className="flex flex-col items-center gap-2 text-gray-500 text-xs">
                  <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
                  <span>Loading canvas...</span>
                </div>
              )}
            </div>

            {/* Explanatory Banner */}
            <div className="bg-dark-850 border border-gray-800 rounded-xl p-3 flex items-start gap-2.5 text-xs text-gray-400 leading-relaxed">
              <Info className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-gray-200 block mb-0.5">How default styles work:</strong>
                When you add new shows to Plex, PlexCards seeds their card generator with this typography and layout.
                You can always customize individual shows independently in their own Show Studio at any time.
              </div>
            </div>

            {/* Quick Reset Button */}
            <div className="pt-1 flex items-center justify-between">
              <button
                type="button"
                onClick={handleResetToBaseline}
                className="text-xs text-gray-400 hover:text-white flex items-center gap-1.5 transition px-2.5 py-1.5 rounded-lg bg-dark-800 border border-gray-700 hover:border-gray-600"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset to Baseline System Defaults</span>
              </button>

              <div className="flex items-center gap-1.5 text-[11px] text-gray-500">
                <Sparkles className="w-3 h-3 text-purple-400" />
                <span>AI suggestions disabled for clean defaults</span>
              </div>
            </div>
          </div>

          {/* Right Column: Styling Controls (No Gemini, purely clean defaults) */}
          <div className="w-full lg:col-span-5 p-3 sm:p-5 flex flex-col gap-5 shrink-0 lg:shrink lg:overflow-y-auto min-h-0 bg-dark-900">
            {isLoading ? (
              <div className="py-16 flex flex-col items-center justify-center gap-2 text-gray-500 text-xs">
                <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
                <span>Loading configuration...</span>
              </div>
            ) : (
              <GeneratorControls
                styleConfig={styleConfig}
                setStyleConfig={setStyleConfig}
                applyPreset={applyPreset}
                aiPrompt=""
                setAiPrompt={() => {}}
                handleAiSuggest={() => {}}
                isAiLoading={false}
                aiReasoning=""
                isEpisodesLoading={false}
                activeShowHasCustomStyle={true}
                availableFonts={availableFonts}
                isUploadingFont={isUploadingFont}
                handleFontUpload={handleFontUpload}
                handleSaveStyle={handleSave}
                isSavedJustNow={isSavedJustNow}
                hasGeminiKey={false}
                activeShowRatingKey={undefined}
              />
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 sm:px-6 py-3 border-t border-gray-800 flex items-center justify-between bg-dark-850 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-medium text-gray-400 hover:text-white transition"
          >
            Cancel
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving}
              className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-bold px-5 py-2 rounded-lg text-xs transition flex items-center gap-1.5 shadow-md shadow-brand-500/20"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : isSavedJustNow ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-950" />
              ) : (
                <Sliders className="w-4 h-4" />
              )}
              <span>{isSavedJustNow ? 'Saved Default!' : 'Save as Default Style'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
