import React, { useRef } from 'react';
import { Sparkles, Loader2, Upload, CheckCircle } from 'lucide-react';
import { StyleConfig } from '../../types';

export const getSubheadingPreview = (
  fmt?: string,
  icon?: string,
  casing?: 'upper' | 'title' | 'lower'
): string => {
  const sep = icon === 'none' ? '' : (icon || '•');
  let result = '';

  const applyCasing = (str: string) => {
    if (casing === 'title') {
      return str
        .toLowerCase()
        .replace(/\b([a-z])/g, (m) => m.toUpperCase())
        .replace(/\bS(\d+)\b/gi, (_, d) => `S${d.padStart(2, '0')}`)
        .replace(/\bE(\d+)\b/gi, (_, d) => `E${d.padStart(2, '0')}`);
    } else if (casing === 'lower') {
      return str.toLowerCase();
    }
    return str.toUpperCase();
  };

  switch (fmt) {
    case 'season_word_ep_word':
      result = `SEASON ONE ${sep ? sep + ' ' : ''}EPISODE FIVE`.trim();
      break;
    case 'season_num_ep_num':
      result = `SEASON 1 ${sep ? sep + ' ' : ''}EPISODE 5`.trim();
      break;
    case 's_pad_ep_num':
      result = `S01 ${sep ? sep + ' ' : ''}EPISODE 5`.trim();
      break;
    case 's_pad_ep_pad':
      result = `S01 ${sep ? sep + ' ' : ''}EPISODE 05`.trim();
      break;
    case 's_pad_e_pad':
      result = `S01 ${sep ? sep + ' ' : ''}E05`.trim();
      break;
    case 'compact_pad':
      result = 'S01E05';
      break;
    case 'ep_num':
      result = 'EPISODE 5';
      break;
    case 'ep_word':
      result = 'EPISODE FIVE';
      break;
    case 'e_pad':
      result = 'E05';
      break;
    case 'season_num':
      result = 'SEASON 1';
      break;
    case 'season_word':
      result = 'SEASON ONE';
      break;
    default:
      if (fmt && fmt.includes('{')) {
        result = fmt
          .replace(/\{season\}|\{s_num\}|\{s\}/gi, '1')
          .replace(/\{season_pad\}|\{s_pad\}/gi, '01')
          .replace(/\{season_word\}|\{s_word\}/gi, 'ONE')
          .replace(/\{episode\}|\{e_num\}|\{e\}/gi, '5')
          .replace(/\{episode_pad\}|\{e_pad\}/gi, '05')
          .replace(/\{episode_word\}|\{e_word\}/gi, 'FIVE')
          .replace(/\{icon\}|\{sep\}/gi, sep)
          .trim();
      } else if (fmt) {
        result = fmt;
      } else {
        result = `SEASON 1 ${sep ? sep + ' ' : ''}EPISODE 5`.trim();
      }
      break;
  }

  return applyCasing(result);
};

interface GeneratorControlsProps {
  styleConfig: StyleConfig;
  setStyleConfig: React.Dispatch<React.SetStateAction<StyleConfig>>;
  applyPreset: (preset: 'cinematic' | 'clean_bottom') => void;
  aiPrompt: string;
  setAiPrompt: (prompt: string) => void;
  handleAiSuggest: () => void;
  isAiLoading: boolean;
  aiReasoning: string;
  isEpisodesLoading: boolean;
  activeShowHasCustomStyle: boolean;
  availableFonts: Array<{ name: string; type: string }>;
  isUploadingFont: boolean;
  handleFontUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleSaveStyle: () => void;
  isSavedJustNow: boolean;
  hasGeminiKey?: boolean;
}

const PREDEFINED_FORMATS = [
  'season_num_ep_num',
  's_pad_ep_num',
  's_pad_ep_pad',
  's_pad_e_pad',
  'season_word_ep_word',
  'compact_pad',
  'ep_num',
  'ep_word',
  'e_pad',
  'season_num',
  'season_word',
  's_pad'
];

export const GeneratorControls: React.FC<GeneratorControlsProps> = ({
  styleConfig,
  setStyleConfig,
  applyPreset,
  aiPrompt,
  setAiPrompt,
  handleAiSuggest,
  isAiLoading,
  aiReasoning,
  isEpisodesLoading,
  activeShowHasCustomStyle,
  availableFonts,
  isUploadingFont,
  handleFontUpload,
  handleSaveStyle,
  isSavedJustNow,
  hasGeminiKey = true
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isCustomFormat = !PREDEFINED_FORMATS.includes(styleConfig.subheading_format);

  return (
    <div className="border-t border-gray-800 pt-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Generator Styling
        </label>
        <div className="flex items-center gap-1 text-[11px]">
          <button
            type="button"
            onClick={() => applyPreset('cinematic')}
            className="px-2 py-0.5 rounded bg-gray-800 text-gray-300 hover:bg-gray-700"
          >
            Cinematic
          </button>
          <button
            type="button"
            onClick={() => applyPreset('clean_bottom')}
            className="px-2 py-0.5 rounded bg-gray-800 text-gray-300 hover:bg-gray-700"
          >
            Bottom Center
          </button>
        </div>
      </div>

      {/* AI Assistant */}
      {hasGeminiKey && (
        <div className="bg-dark-850 border border-purple-500/30 rounded-xl p-3 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-purple-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-purple-400" /> AI Style Assistant
            </span>
            <span className="text-[10px] text-gray-500">Gemini 3.5 Flash Lite</span>
          </div>
          {isEpisodesLoading && !activeShowHasCustomStyle ? (
            <div className="bg-purple-950/40 border border-purple-500/30 rounded-lg p-2.5 flex items-center gap-2 text-xs text-purple-300 animate-pulse">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400 shrink-0" />
              <span>Gemini is analyzing show tone to recommend initial styling...</span>
            </div>
          ) : (
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g., Gritty thriller with bold gold font (or leave blank to auto-match)..."
                title="Gemini automatically analyzes the show's poster, genres, and synopsis. Type here only if you want to give custom styling directions."
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAiSuggest()}
                className="flex-1 bg-dark-900 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              />
              <button
                type="button"
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
      )}

      {/* Text Positioning */}
      <div>
        <label className="text-[11px] text-gray-400 block mb-1">Text Position</label>
        <select
          value={styleConfig.text_position}
          onChange={(e) => {
            const pos = e.target.value as any;
            let grad: 'left' | 'right' | 'bottom' | 'top' | 'center' = 'left';
            if (pos.includes('top')) grad = 'top';
            else if (pos.includes('bottom')) grad = 'bottom';
            else if (pos.includes('right')) grad = 'right';
            else if (pos === 'center') grad = 'center';
            setStyleConfig((prev) => ({
              ...prev,
              text_position: pos,
              gradient_side: grad
            }));
          }}
          className="w-full bg-dark-800 border border-gray-700 text-xs rounded-lg px-3 py-2 text-white focus:outline-none focus:border-brand-500"
        >
          <option value="left_bottom">Bottom Left</option>
          <option value="center_bottom">Bottom Center</option>
          <option value="right_bottom">Bottom Right</option>
          <option value="left_center">Left Middle (Center Left)</option>
          <option value="center">Center</option>
          <option value="right_center">Right Middle (Center Right)</option>
          <option value="top_left">Top Left</option>
          <option value="top_center">Top Center</option>
          <option value="top_right">Top Right</option>
        </select>
      </div>

      {/* Text Box Width */}
      <div>
        <div className="flex justify-between text-[11px] text-gray-400 mb-1">
          <span>Text Box Width</span>
          <span className="font-mono text-gray-300">
            {styleConfig.text_box_width_pct || 42}% of still
            {(!styleConfig.text_box_width_pct || styleConfig.text_box_width_pct === 42) && (
              <span className="text-brand-400 ml-1 font-sans text-[10px]">(Default)</span>
            )}
            {styleConfig.text_box_width_pct === 50 && (
              <span className="text-emerald-400 ml-1 font-sans text-[10px]">(50% Half)</span>
            )}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min="35"
            max="75"
            step="1"
            value={styleConfig.text_box_width_pct || 42}
            onChange={(e) =>
              setStyleConfig((prev) => ({
                ...prev,
                text_box_width_pct: Number(e.target.value)
              }))
            }
            className="w-full accent-brand-500 bg-dark-800 cursor-pointer"
          />
          <input
            type="number"
            min="35"
            max="75"
            value={styleConfig.text_box_width_pct || 42}
            onChange={(e) => {
              const val = Math.max(35, Math.min(75, Number(e.target.value) || 42));
              setStyleConfig((prev) => ({
                ...prev,
                text_box_width_pct: val
              }));
            }}
            className="w-14 bg-dark-800 border border-gray-700 text-xs rounded px-2 py-1 text-white text-center font-mono"
          />
        </div>
        <div className="flex justify-between text-[10px] text-gray-500 mt-1">
          <button
            type="button"
            onClick={() => setStyleConfig((prev) => ({ ...prev, text_box_width_pct: 42 }))}
            className={`hover:text-white transition ${(!styleConfig.text_box_width_pct || styleConfig.text_box_width_pct === 42) ? 'text-brand-400 font-semibold' : ''}`}
          >
            Default (42%)
          </button>
          <button
            type="button"
            onClick={() => setStyleConfig((prev) => ({ ...prev, text_box_width_pct: 50 }))}
            className={`hover:text-white transition ${styleConfig.text_box_width_pct === 50 ? 'text-emerald-400 font-semibold' : ''}`}
          >
            Half Still (50%)
          </button>
          <button
            type="button"
            onClick={() => setStyleConfig((prev) => ({ ...prev, text_box_width_pct: 65 }))}
            className={`hover:text-white transition ${styleConfig.text_box_width_pct === 65 ? 'text-white font-semibold' : ''}`}
          >
            Wide (65%)
          </button>
        </div>
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

      {/* Title Font Size */}
      <div>
        <div className="flex justify-between text-[11px] text-gray-400 mb-1">
          <span>Title Font Size</span>
          <span className="font-mono text-gray-300">{styleConfig.title_font_size || 82}px</span>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="range"
            min="40"
            max="140"
            value={styleConfig.title_font_size || 82}
            onChange={(e) =>
              setStyleConfig((prev) => ({
                ...prev,
                title_font_size: Number(e.target.value)
              }))
            }
            className="w-full accent-brand-500 bg-dark-800 cursor-pointer"
          />
          <input
            type="number"
            min="40"
            max="140"
            value={styleConfig.title_font_size || 82}
            onChange={(e) => {
              const val = Math.max(40, Math.min(140, Number(e.target.value) || 82));
              setStyleConfig((prev) => ({
                ...prev,
                title_font_size: val
              }));
            }}
            className="w-14 bg-dark-800 border border-gray-700 text-xs rounded px-2 py-1 text-white text-center font-mono"
          />
        </div>
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
                className="font-bold tracking-wide"
                style={{
                  color: styleConfig.subheading_color,
                  fontFamily: styleConfig.subheading_font_family || styleConfig.font_family,
                  letterSpacing: `${styleConfig.subheading_tracking || 0}px`
                }}
              >
                {getSubheadingPreview(styleConfig.subheading_format, styleConfig.subheading_icon, styleConfig.subheading_casing)}
              </span>
            </div>

            {/* Position & Text Casing Controls */}
            <div className="grid grid-cols-2 gap-2">
              {/* Subheading Position */}
              <div>
                <label className="text-[11px] text-gray-400 block mb-1 font-medium">Position</label>
                <div className="grid grid-cols-2 gap-1 bg-dark-950 p-1 rounded-lg border border-gray-800">
                  <button
                    type="button"
                    onClick={() =>
                      setStyleConfig((prev) => ({
                        ...prev,
                        subheading_position: 'above'
                      }))
                    }
                    className={`py-1 text-xs rounded font-medium transition text-center ${
                      (styleConfig.subheading_position || 'above') === 'above'
                        ? 'bg-brand-600 text-white shadow-sm'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    Above Title
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setStyleConfig((prev) => ({
                        ...prev,
                        subheading_position: 'below'
                      }))
                    }
                    className={`py-1 text-xs rounded font-medium transition text-center ${
                      styleConfig.subheading_position === 'below'
                        ? 'bg-brand-600 text-white shadow-sm'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    Below Title
                  </button>
                </div>
              </div>

              {/* Text Casing */}
              <div>
                <label className="text-[11px] text-gray-400 block mb-1 font-medium">Text Casing</label>
                <div className="grid grid-cols-3 gap-1 bg-dark-950 p-1 rounded-lg border border-gray-800">
                  {[
                    { id: 'upper', label: 'UPPER' },
                    { id: 'title', label: 'Title' },
                    { id: 'lower', label: 'lower' }
                  ].map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() =>
                        setStyleConfig((prev) => ({
                          ...prev,
                          subheading_casing: item.id as any
                        }))
                      }
                      className={`py-1 text-xs rounded font-medium transition text-center ${
                        (styleConfig.subheading_casing || 'upper') === item.id
                          ? 'bg-brand-600 text-white shadow-sm'
                          : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Subtitle Font Family Selector */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] text-gray-400 font-medium">Subtitle Font</label>
                {styleConfig.subheading_font_family && styleConfig.subheading_font_family !== styleConfig.font_family && (
                  <button
                    type="button"
                    onClick={() =>
                      setStyleConfig((prev) => ({
                        ...prev,
                        subheading_font_family: undefined
                      }))
                    }
                    className="text-[10px] text-brand-400 hover:underline"
                  >
                    Reset to Match Title
                  </button>
                )}
              </div>
              <select
                value={styleConfig.subheading_font_family || ''}
                onChange={(e) =>
                  setStyleConfig((prev) => ({
                    ...prev,
                    subheading_font_family: e.target.value || undefined
                  }))
                }
                className="w-full bg-dark-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-brand-500 font-medium"
              >
                <option value="">Match Title Font ({styleConfig.font_family})</option>
                {styleConfig.subheading_font_family &&
                  !availableFonts.some(
                    (f) => f.name.toLowerCase() === styleConfig.subheading_font_family?.toLowerCase()
                  ) && (
                    <option value={styleConfig.subheading_font_family}>
                      {styleConfig.subheading_font_family} (Auto-downloaded / AI suggested)
                    </option>
                  )}
                <optgroup label="Installed & Google Fonts">
                  {availableFonts.map((f) => (
                    <option key={f.name} value={f.name}>
                      {f.name} {f.type === 'custom' ? '(Custom)' : ''}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            {/* Subheading Format Selector */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] text-gray-400 font-medium">Format Style</label>
                {isCustomFormat && (
                  <span className="text-[10px] text-brand-400 font-medium">Custom Template Active</span>
                )}
              </div>
              <select
                value={isCustomFormat ? 'custom' : styleConfig.subheading_format}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'custom') {
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_format: prev.subheading_format && prev.subheading_format.includes('{')
                        ? prev.subheading_format
                        : '{s_pad} • Episode {episode}'
                    }));
                  } else {
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_format: val
                    }));
                  }
                }}
                className="w-full bg-dark-800 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-brand-500 font-medium"
              >
                <option value="season_num_ep_num">Season 1 • Episode 1 (Standard)</option>
                <option value="s_pad_ep_num">S01 • Episode 1</option>
                <option value="s_pad_ep_pad">S01 • Episode 01</option>
                <option value="s_pad_e_pad">S01 • E01 (Short Code)</option>
                <option value="season_word_ep_word">Season One • Episode One (Words)</option>
                <option value="compact_pad">S01E01 (Compact)</option>
                <option value="ep_num">Episode 1 (Episode Only - No Season)</option>
                <option value="ep_word">Episode One (Episode Only - No Season)</option>
                <option value="e_pad">E01 (Episode Code Only - No Season)</option>
                <option value="season_num">Season 1 (Season Only)</option>
                <option value="custom">Custom Template...</option>
              </select>

              {/* Quick Format Chips */}
              <div className="flex flex-wrap gap-1 mt-1.5">
                {[
                  { id: 'season_num_ep_num', label: 'Season 1 • Ep 1' },
                  { id: 's_pad_ep_num', label: 'S01 • Ep 1' },
                  { id: 's_pad_e_pad', label: 'S01 • E01' },
                  { id: 'ep_num', label: 'Episode 1' },
                  { id: 'e_pad', label: 'E01' },
                  { id: 'compact_pad', label: 'S01E01' },
                  { id: 'custom', label: 'Custom' }
                ].map((chip) => {
                  const isSelected = chip.id === 'custom' ? isCustomFormat : styleConfig.subheading_format === chip.id;
                  return (
                    <button
                      key={chip.id}
                      type="button"
                      onClick={() => {
                        if (chip.id === 'custom') {
                          setStyleConfig((prev) => ({
                            ...prev,
                            subheading_format: prev.subheading_format && prev.subheading_format.includes('{')
                              ? prev.subheading_format
                              : '{s_pad} • Episode {episode}'
                          }));
                        } else {
                          setStyleConfig((prev) => ({
                            ...prev,
                            subheading_format: chip.id
                          }));
                        }
                      }}
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

              {/* Custom Template Editor */}
              {isCustomFormat && (
                <div className="mt-2 p-2.5 bg-dark-950 border border-gray-800 rounded-lg space-y-2">
                  <div className="flex justify-between items-center text-[10px]">
                    <span className="text-gray-400 font-medium">Custom Template Pattern</span>
                    <span className="text-gray-500">Click pill to append</span>
                  </div>
                  <input
                    type="text"
                    value={styleConfig.subheading_format}
                    onChange={(e) =>
                      setStyleConfig((prev) => ({
                        ...prev,
                        subheading_format: e.target.value
                      }))
                    }
                    placeholder="e.g. Series {season} • Ep {episode}"
                    className="w-full bg-dark-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-brand-500"
                  />
                  <div className="flex flex-wrap gap-1">
                    {[
                      { tag: '{s_pad}', label: 'S01' },
                      { tag: '{episode}', label: 'Ep 1' },
                      { tag: '{e_pad}', label: '01' },
                      { tag: '{season}', label: 'Season 1' },
                      { tag: '{icon}', label: 'Sep Icon' },
                      { tag: '{season_word}', label: 'One' },
                      { tag: '{episode_word}', label: 'Five' }
                    ].map((pill) => (
                      <button
                        key={pill.tag}
                        type="button"
                        onClick={() =>
                          setStyleConfig((prev) => ({
                            ...prev,
                            subheading_format: (prev.subheading_format ? `${prev.subheading_format} ` : '') + pill.tag
                          }))
                        }
                        className="text-[10px] bg-dark-800 border border-gray-700 px-1.5 py-0.5 rounded text-gray-300 hover:text-brand-400 hover:border-brand-500/40 font-mono transition"
                        title={`Append ${pill.tag}`}
                      >
                        {pill.tag}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Separator - only show when both season and episode are visible or custom */}
            {(!['ep_num', 'ep_word', 'e_pad', 'season_num', 'season_word', 's_pad', 'compact_pad'].includes(styleConfig.subheading_format) || isCustomFormat) && (
              <div>
                <label className="text-[11px] text-gray-400 block mb-1.5 font-medium">
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

            {/* Letter Spacing (Tracking) */}
            <div>
              <div className="flex justify-between text-[11px] text-gray-400 mb-1">
                <span>Letter Spacing (Tracking)</span>
                <span className="font-mono text-gray-300">{styleConfig.subheading_tracking || 0}px</span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0"
                  max="8"
                  value={styleConfig.subheading_tracking || 0}
                  onChange={(e) =>
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_tracking: Number(e.target.value)
                    }))
                  }
                  className="w-full accent-brand-500 bg-dark-800 cursor-pointer"
                />
                <input
                  type="number"
                  min="0"
                  max="8"
                  value={styleConfig.subheading_tracking || 0}
                  onChange={(e) => {
                    const val = Math.max(0, Math.min(8, Number(e.target.value) || 0));
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_tracking: val
                    }));
                  }}
                  className="w-14 bg-dark-800 border border-gray-700 text-xs rounded px-2 py-1 text-white text-center font-mono"
                />
              </div>
            </div>

            {/* Subheading Font Size */}
            <div>
              <div className="flex justify-between text-[11px] text-gray-400 mb-1">
                <span>Subheading Font Size</span>
                <span className="font-mono text-gray-300">{styleConfig.subheading_font_size || 34}px</span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="20"
                  max="60"
                  value={styleConfig.subheading_font_size || 34}
                  onChange={(e) =>
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_font_size: Number(e.target.value)
                    }))
                  }
                  className="w-full accent-brand-500 bg-dark-800 cursor-pointer"
                />
                <input
                  type="number"
                  min="20"
                  max="60"
                  value={styleConfig.subheading_font_size || 34}
                  onChange={(e) => {
                    const val = Math.max(20, Math.min(60, Number(e.target.value) || 34));
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_font_size: val
                    }));
                  }}
                  className="w-14 bg-dark-800 border border-gray-700 text-xs rounded px-2 py-1 text-white text-center font-mono"
                />
              </div>
            </div>

            {/* Subheading Distance to Title */}
            <div>
              <div className="flex justify-between text-[11px] text-gray-400 mb-1">
                <span>Distance to Title (Gap)</span>
                <span className="font-mono text-gray-300">{styleConfig.subheading_gap !== undefined ? styleConfig.subheading_gap : 12}px</span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0"
                  max="48"
                  value={styleConfig.subheading_gap !== undefined ? styleConfig.subheading_gap : 12}
                  onChange={(e) =>
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_gap: Number(e.target.value)
                    }))
                  }
                  className="w-full accent-brand-500 bg-dark-800 cursor-pointer"
                />
                <input
                  type="number"
                  min="0"
                  max="48"
                  value={styleConfig.subheading_gap !== undefined ? styleConfig.subheading_gap : 12}
                  onChange={(e) => {
                    const val = Math.max(0, Math.min(48, Number(e.target.value) || 0));
                    setStyleConfig((prev) => ({
                      ...prev,
                      subheading_gap: val
                    }));
                  }}
                  className="w-14 bg-dark-800 border border-gray-700 text-xs rounded px-2 py-1 text-white text-center font-mono"
                />
              </div>
              <div className="flex justify-between text-[10px] text-gray-500 mt-1">
                <button
                  type="button"
                  onClick={() => setStyleConfig((prev) => ({ ...prev, subheading_gap: 4 }))}
                  className={`hover:text-white transition ${styleConfig.subheading_gap === 4 ? 'text-brand-400 font-semibold' : ''}`}
                >
                  Tight (4px)
                </button>
                <button
                  type="button"
                  onClick={() => setStyleConfig((prev) => ({ ...prev, subheading_gap: 12 }))}
                  className={`hover:text-white transition ${(styleConfig.subheading_gap === undefined || styleConfig.subheading_gap === 12) ? 'text-emerald-400 font-semibold' : ''}`}
                >
                  Default (12px)
                </button>
                <button
                  type="button"
                  onClick={() => setStyleConfig((prev) => ({ ...prev, subheading_gap: 20 }))}
                  className={`hover:text-white transition ${styleConfig.subheading_gap === 20 ? 'text-white font-semibold' : ''}`}
                >
                  Relaxed (20px)
                </button>
                <button
                  type="button"
                  onClick={() => setStyleConfig((prev) => ({ ...prev, subheading_gap: 32 }))}
                  className={`hover:text-white transition ${styleConfig.subheading_gap === 32 ? 'text-white font-semibold' : ''}`}
                >
                  Wide (32px)
                </button>
              </div>
            </div>

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
  );
};
