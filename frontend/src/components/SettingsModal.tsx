import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { useToast } from '../context/ToastContext';
import { DefaultStyleModal } from './DefaultStyleModal';
import {
  Settings,
  X,
  Sparkles,
  Ban,
  Zap,
  Wand2,
  FlaskConical,
  CheckCircle2,
  Loader2,
  AlertTriangle,
  Star,
  Plus,
  Sliders,
  Film,
  Palette
} from 'lucide-react';

interface SettingsModalProps {
  onClose: () => void;
  onShowsUpdated: () => void;
  testMode: boolean;
  tvLibrary: string;
  listenerConnected?: boolean;
  hasGeminiKey?: boolean;
  hasTvdbKey?: boolean;
  hasTmdbKey?: boolean;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  onClose,
  onShowsUpdated,
  testMode,
  tvLibrary,
  listenerConnected = false,
  hasGeminiKey = true,
  hasTvdbKey = false,
  hasTmdbKey = true
}) => {
  const { showToast } = useToast();
  const [autoGemini, setAutoGemini] = useState<boolean>(true);
  const [autoSmartPick, setAutoSmartPick] = useState<boolean>(true);
  const [providerPriority, setProviderPriority] = useState<string>('tvdb');
  const [defaultMode, setDefaultMode] = useState<string>('ignored');
  const [preferredCreators, setPreferredCreators] = useState<string>('');
  const [newCreatorInput, setNewCreatorInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isBulking, setIsBulking] = useState<boolean>(false);
  const [isDefaultStyleModalOpen, setIsDefaultStyleModalOpen] = useState<boolean>(false);
  const [defaultStyleSummary, setDefaultStyleSummary] = useState<string>('Oswald • 108px');

  const refreshDefaultStyleSummary = () => {
    api.getDefaultStyle()
      .then((res) => {
        if (res.style) {
          const pos = (res.style.text_position || 'left_center').replace('_', ' ');
          setDefaultStyleSummary(`${res.style.font_family || 'Oswald'} • ${res.style.title_font_size || 108}px • ${pos}`);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    let mounted = true;
    api.getSettings()
      .then((data) => {
        if (!mounted) return;
        const s = data.settings || {};
        setAutoGemini(s.auto_gemini_suggestion !== 'false');
        setAutoSmartPick(s.auto_smart_pick_stills !== 'false');
        setDefaultMode(s.default_new_show_mode || 'ignored');
        setPreferredCreators(s.preferred_mediux_creators || '');
        setProviderPriority(s.metadata_provider_priority || 'tvdb');
      })
      .catch((err) => console.error('Failed to load settings:', err))
      .finally(() => {
        if (mounted) setIsLoading(false);
      });

    refreshDefaultStyleSummary();

    return () => {
      mounted = false;
    };
  }, []);

  const creatorList = preferredCreators
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean);

  const handleAddCreator = (creator: string) => {
    const trimmed = creator.trim();
    if (!trimmed) return;
    if (creatorList.some((c) => c.toLowerCase() === trimmed.toLowerCase())) {
      showToast({
        type: 'info',
        title: 'Already Added',
        message: `"${trimmed}" is already in your preferred creators list.`
      });
      setNewCreatorInput('');
      return;
    }
    const updated = [...creatorList, trimmed].join(', ');
    setPreferredCreators(updated);
    setNewCreatorInput('');
    handleSaveSetting('preferred_mediux_creators', updated);
  };

  const handleRemoveCreator = (creatorToRemove: string) => {
    const updated = creatorList
      .filter((c) => c.toLowerCase() !== creatorToRemove.toLowerCase())
      .join(', ');
    setPreferredCreators(updated);
    handleSaveSetting('preferred_mediux_creators', updated);
  };

  const handleSaveSetting = async (key: string, value: string) => {
    setIsSaving(true);
    try {
      await api.updateSettings({ [key]: value });
      showToast({
        type: 'success',
        title: 'Settings Saved',
        message: 'Your preferences have been updated.'
      });
    } catch (err) {
      showToast({
        type: 'error',
        title: 'Save Failed',
        message: String(err)
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleBulkSetMode = async (mode: string) => {
    if (!confirm(`Are you sure you want to set ALL shows in your library to "${mode.toUpperCase()}"?`)) {
      return;
    }
    setIsBulking(true);
    try {
      const res = await api.bulkSetMode(mode);
      showToast({
        type: 'success',
        title: 'Bulk Update Complete',
        message: `Updated all ${res.updated_count} shows to ${mode}.`
      });
      onShowsUpdated();
    } catch (err) {
      showToast({
        type: 'error',
        title: 'Bulk Update Failed',
        message: String(err)
      });
    } finally {
      setIsBulking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-dark-900 border border-gray-800 rounded-xl sm:rounded-2xl w-full max-w-xl max-h-[92dvh] sm:max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-4 sm:px-6 py-3.5 sm:py-4 border-b border-gray-800 flex items-center justify-between bg-dark-850 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-500/20 text-brand-500 flex items-center justify-center font-bold">
              <Settings className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Application Settings</h2>
              <p className="text-xs text-gray-400">Manage automation, Gemini AI styling, and defaults</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-2 rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 space-y-6 flex-1 min-h-0 overflow-y-auto">
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center gap-2 text-gray-500 text-xs">
              <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
              <span>Loading settings...</span>
            </div>
          ) : (
            <>
              {/* Section 1: AI Automation */}
              {hasGeminiKey !== false ? (
                <div className="bg-dark-850 border border-gray-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-purple-400" />
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-300">
                        Gemini AI Styling
                      </h3>
                    </div>
                    <span className="text-[10px] text-gray-500">Gemini 3.5 Flash Lite</span>
                  </div>

                  <div className="flex items-start justify-between gap-4 pt-1">
                    <div>
                      <span className="text-xs font-semibold text-white block">
                        Auto-suggest styles for unconfigured shows
                      </span>
                      <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">
                        When opening a show that hasn't had a style preset saved yet, automatically ask Gemini
                        to recommend typography, colors, and layout based on TMDb genres & overview.
                      </p>
                    </div>

                    {/* Toggle Switch */}
                    <button
                      type="button"
                      onClick={() => {
                        const next = !autoGemini;
                        setAutoGemini(next);
                        handleSaveSetting('auto_gemini_suggestion', next ? 'true' : 'false');
                      }}
                      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                        autoGemini ? 'bg-purple-600' : 'bg-gray-700'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                          autoGemini ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="bg-dark-850/60 border border-gray-800 rounded-xl p-3 sm:p-4 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <Sparkles className="w-4 h-4 text-gray-600 shrink-0" />
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                        Gemini AI Styling
                      </h3>
                      <p className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">
                        Disabled. Set <code className="text-gray-400 font-mono">GEMINI_API_KEY</code> in <code className="text-gray-400 font-mono">.env</code> to enable AI typography & color styling.
                      </p>
                    </div>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700 shrink-0">
                    Not Configured
                  </span>
                </div>
              )}

              {/* Section: Smart Auto-Pick Stills */}
              <div className="bg-dark-850 border border-gray-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Film className="w-4 h-4 text-purple-400" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-300">
                      Smart Auto-Pick Stills
                    </h3>
                  </div>
                  <span className="text-[10px] text-gray-500">TMDb Quality Scored</span>
                </div>

                <div className="flex items-start justify-between gap-4 pt-1">
                  <div>
                    <span className="text-xs font-semibold text-white block">
                      Auto-select highest community-rated 16:9 frame
                    </span>
                    <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">
                      When generating cards, automatically evaluate all available candidate stills by community rating and native 16:9 aspect ratio to select the optimal frame instead of TMDb's first upload.
                    </p>
                  </div>

                  {/* Toggle Switch */}
                  <button
                    type="button"
                    onClick={() => {
                      const next = !autoSmartPick;
                      setAutoSmartPick(next);
                      handleSaveSetting('auto_smart_pick_stills', next ? 'true' : 'false');
                    }}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      autoSmartPick ? 'bg-purple-600' : 'bg-gray-700'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                        autoSmartPick ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              </div>

              {/* Section: Metadata & Still Provider Priority */}
              <div className="bg-dark-850 border border-gray-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-brand-400" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-brand-400">
                      Primary Metadata & Still Provider
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${hasTvdbKey ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-gray-800 text-gray-400 border-gray-700'}`}>
                      TVDB: {hasTvdbKey ? 'Active' : 'Not Configured'}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${hasTmdbKey !== false ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-gray-800 text-gray-400 border-gray-700'}`}>
                      TMDb: {hasTmdbKey !== false ? 'Active' : 'Not Configured'}
                    </span>
                  </div>
                </div>

                <p className="text-[11px] text-gray-400 leading-relaxed">
                  Select which service is queried first when searching for episode stills (screencaps), titles, and artwork. If the primary provider has no still, the secondary provider is automatically used as a fallback.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setProviderPriority('tvdb');
                      handleSaveSetting('metadata_provider_priority', 'tvdb');
                    }}
                    className={`p-3 rounded-lg border text-left transition flex flex-col justify-between gap-1.5 ${
                      providerPriority === 'tvdb'
                        ? 'bg-brand-500/10 border-brand-500 text-white'
                        : 'bg-dark-900 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white flex items-center gap-1.5">
                        TheTVDB (Recommended)
                        {providerPriority === 'tvdb' && <CheckCircle2 className="w-3.5 h-3.5 text-brand-400" />}
                      </span>
                      <span className="text-[10px] text-brand-300 font-mono">TVDB v4</span>
                    </div>
                    <p className="text-[11px] text-gray-400">
                      Best for libraries managed with Sonarr and Plex TVDB ordering. Highest episode screencap coverage.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setProviderPriority('tmdb');
                      handleSaveSetting('metadata_provider_priority', 'tmdb');
                    }}
                    className={`p-3 rounded-lg border text-left transition flex flex-col justify-between gap-1.5 ${
                      providerPriority === 'tmdb'
                        ? 'bg-brand-500/10 border-brand-500 text-white'
                        : 'bg-dark-900 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white flex items-center gap-1.5">
                        The Movie Database
                        {providerPriority === 'tmdb' && <CheckCircle2 className="w-3.5 h-3.5 text-brand-400" />}
                      </span>
                      <span className="text-[10px] text-blue-300 font-mono">TMDb</span>
                    </div>
                    <p className="text-[11px] text-gray-400">
                      Best for libraries configured with native TMDb episode ordering and community quality ratings.
                    </p>
                  </button>
                </div>
              </div>

              {/* Section 2: Default Mode for New Shows */}
              <div className="bg-dark-850 border border-gray-800 rounded-xl p-4 space-y-3">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 block mb-1">
                    Default Mode for Newly Scanned Shows
                  </h3>
                  <p className="text-[11px] text-gray-400 leading-relaxed">
                    When new shows are indexed from Plex, they will start in this mode:
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-1">
                  {[
                    { id: 'ignored', label: 'Ignored', icon: Ban, color: 'text-gray-400' },
                    { id: 'auto', label: 'Auto (MediUX)', icon: Zap, color: 'text-emerald-400' },
                    { id: 'generator_only', label: 'Generator Only', icon: Wand2, color: 'text-purple-400' }
                  ].map((item) => {
                    const isSelected = defaultMode === item.id;
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          setDefaultMode(item.id);
                          handleSaveSetting('default_new_show_mode', item.id);
                        }}
                        className={`border rounded-lg p-2.5 text-center text-xs font-medium transition flex flex-col items-center gap-1.5 ${
                          isSelected
                            ? 'bg-brand-500/15 border-brand-500 text-white font-bold'
                            : 'bg-dark-800 border-gray-700 text-gray-400 hover:text-white'
                        }`}
                      >
                        <Icon className={`w-4 h-4 ${item.color}`} />
                        <span>{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Section: Default Title Card Style */}
              <div className="bg-dark-850 border border-gray-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-brand-400" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-brand-300">
                      Default Title Card Style
                    </h3>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/15 text-brand-400 border border-brand-500/30 font-medium">
                    Universal Template
                  </span>
                </div>

                <p className="text-[11px] text-gray-400 leading-relaxed">
                  Configure the default typography, sizing, layout, colors, and effects automatically seeded into newly scanned shows:
                </p>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-dark-900 border border-gray-800 rounded-lg p-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-brand-500/15 border border-brand-500/30 flex items-center justify-center text-brand-400 shrink-0">
                      <Palette className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">Active Default Template</div>
                      <div className="text-[11px] text-gray-400 font-mono capitalize mt-0.5">{defaultStyleSummary}</div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsDefaultStyleModalOpen(true)}
                    className="px-3 py-1.5 rounded-lg bg-brand-500 hover:bg-brand-600 text-dark-950 text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-sm shrink-0"
                  >
                    <Sliders className="w-3.5 h-3.5" />
                    <span>Customize Default Style</span>
                  </button>
                </div>
              </div>

              {/* Section 3: Preferred MediUX Creators */}
              <div className="bg-dark-850 border border-gray-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Star className="w-4 h-4 text-amber-400 fill-amber-400/30" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-amber-300">
                      Preferred MediUX Creators
                    </h3>
                  </div>
                  <span className="text-[10px] text-gray-500">Auto Prioritized</span>
                </div>

                <p className="text-[11px] text-gray-400 leading-relaxed">
                  When Auto mode searches for sets on MediUX, it will automatically prioritize title cards and season posters uploaded by these creators:
                </p>

                {/* Current Preferred Creators Tags */}
                <div className="flex flex-wrap items-center gap-1.5 pt-1 min-h-[30px]">
                  {creatorList.map((creator) => (
                    <span
                      key={creator}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs font-medium"
                    >
                      <span>{creator}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveCreator(creator)}
                        className="text-amber-400 hover:text-white transition p-0.5 rounded"
                        title={`Remove ${creator}`}
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  {creatorList.length === 0 && (
                    <span className="text-xs text-gray-500 italic">No preferred creators added yet.</span>
                  )}
                </div>

                {/* Add Creator Form */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleAddCreator(newCreatorInput);
                  }}
                  className="flex items-center gap-2 pt-1"
                >
                  <div className="relative flex-1">
                    <input
                      type="text"
                      value={newCreatorInput}
                      onChange={(e) => setNewCreatorInput(e.target.value)}
                      placeholder="Enter creator username (e.g. tallinex, AlanShore60607)..."
                      className="w-full bg-dark-900 border border-gray-700 focus:border-amber-500 focus:ring-1 focus:ring-amber-500 rounded-lg px-3 py-1.5 text-xs text-white placeholder-gray-500 outline-none transition"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={!newCreatorInput.trim()}
                    className="bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition flex items-center gap-1 shrink-0 shadow-sm"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Creator
                  </button>
                </form>
              </div>

              {/* Section 4: Bulk Show Management */}
              <div className="bg-dark-850 border border-gray-800 rounded-xl p-4 space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 block">
                  Bulk Library Actions
                </h3>
                <p className="text-[11px] text-gray-400 leading-relaxed">
                  Quickly batch update all existing shows in your Plex library:
                </p>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => handleBulkSetMode('ignored')}
                    disabled={isBulking}
                    className="bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 text-xs font-medium px-3 py-2 rounded-lg transition flex items-center gap-1.5"
                  >
                    <Ban className="w-3.5 h-3.5 text-gray-400" />
                    <span>Set All Shows to Ignored</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleBulkSetMode('auto')}
                    disabled={isBulking}
                    className="bg-emerald-950/40 hover:bg-emerald-900/50 border border-emerald-500/40 text-emerald-300 text-xs font-medium px-3 py-2 rounded-lg transition flex items-center gap-1.5"
                  >
                    <Zap className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Set All Shows to Auto</span>
                  </button>
                </div>
              </div>

              {/* Section 4: System Information */}
              <div className="bg-dark-850/60 border border-gray-800/80 rounded-xl p-4 text-xs text-gray-400 space-y-2">
                <div className="flex items-center justify-between">
                  <span>Plex TV Library:</span>
                  <strong className="text-white">{tvLibrary || 'TV shows'}</strong>
                </div>
                <div className="flex items-center justify-between">
                  <span>Real-Time Alert Listener:</span>
                  {listenerConnected ? (
                    <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse" />
                      Active (Instant detection via WebSocket)
                    </span>
                  ) : (
                    <span className="text-amber-400 font-semibold flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-400" />
                      Reconnecting...
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span>Safety Gating:</span>
                  {testMode ? (
                    <span className="text-amber-400 font-semibold flex items-center gap-1">
                      <FlaskConical className="w-3.5 h-3.5" /> TEST_MODE=true (Plex uploads simulated)
                    </span>
                  ) : (
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Live Mode (Uploads to Plex enabled)
                    </span>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-800 flex items-center justify-end bg-dark-850">
          <button
            type="button"
            onClick={onClose}
            className="bg-brand-500 hover:bg-brand-600 text-dark-950 font-bold px-4 py-1.5 rounded-lg text-xs transition"
          >
            Done
          </button>
        </div>
      </div>

      {/* Default Generator Style Customizer Modal */}
      {isDefaultStyleModalOpen && (
        <DefaultStyleModal
          onClose={() => setIsDefaultStyleModalOpen(false)}
          onSaved={() => {
            refreshDefaultStyleSummary();
          }}
        />
      )}
    </div>
  );
};
