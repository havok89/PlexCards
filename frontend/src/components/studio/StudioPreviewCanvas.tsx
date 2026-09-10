import React from 'react';
import { Show, Episode, MediuxSet } from '../../types';
import {
  Eye, Zap, Wand2, Loader2, Sparkles, FlaskConical
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
  currentEp
}) => {
  return (
    <div className="w-full lg:col-span-7 p-3 sm:p-5 lg:p-6 flex flex-col gap-3 sm:gap-4 bg-dark-950/40 shrink-0 lg:shrink lg:overflow-y-auto min-h-0">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
            <Eye className="w-4 h-4 text-brand-500" /> Live Preview
          </span>

          {/* View Switcher: MediUX Card vs Generator Fallback */}
          {currentEpMediuxCardUrl && show.mode === 'auto' && (
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

      {/* Preview Frame: Constrained on mobile/tablet, full on desktop */}
      <div className="w-full flex justify-center shrink-0">
        <div className="relative aspect-video w-full max-w-[340px] sm:max-w-[460px] lg:max-w-none bg-dark-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl flex items-center justify-center">
          {activeDisplayUrl ? (
            <img
              src={activeDisplayUrl}
              alt="Title Card Preview"
              className="w-full h-full object-cover"
            />
          ) : isEpisodesLoading && !show.has_custom_style ? (
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
              <span>
                MediUX Card • {activeMediuxSet?.creator}
              </span>
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
        </div>
      </div>

      {currentEp && (
        <div className="bg-dark-900 border border-gray-800 rounded-xl p-2.5 sm:p-3 text-[11px] sm:text-xs text-gray-400 flex items-center justify-between gap-2 shrink-0">
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
  );
};
