import { Episode, Show } from '../../types';
import {
  Sliders, ExternalLink, Edit2, AlertTriangle,
  RefreshCw, X, Loader2, Sparkles, Send
} from 'lucide-react';

interface StudioHeaderProps {
  show: Show;
  currentEp?: Episode;
  onClose: () => void;
  onOpenTmdbModal: () => void;
  onOpenFixMatchModal: () => void;
  updateScope: 'all' | 'missing' | 'current';
  onToggleScope: (scope: 'all' | 'missing' | 'current') => void;
  testMode: boolean;
  isForceLive: boolean;
  onToggleForceLive: (val: boolean) => void;
  isApplying: boolean;
  applyProgress: { current: number; total: number; label?: string } | null;
  onApplyCards: () => void;
}

export const StudioHeader: React.FC<StudioHeaderProps> = ({
  show,
  currentEp,
  onClose,
  onOpenTmdbModal,
  onOpenFixMatchModal,
  updateScope,
  onToggleScope,
  testMode,
  isForceLive,
  onToggleForceLive,
  isApplying,
  applyProgress,
  onApplyCards
}) => {
  return (
    <div className="px-3 sm:px-6 py-2.5 sm:py-4 border-b border-gray-800 bg-dark-850 flex flex-col md:flex-row md:items-center justify-between gap-2.5 sm:gap-3 shrink-0">
      <div className="flex items-start md:items-center justify-between gap-3 min-w-0">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-brand-500/20 text-brand-500 flex items-center justify-center font-bold shrink-0">
            <Sliders className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base sm:text-lg font-bold text-white truncate">
              {show.title}
            </h2>
            <div className="flex items-center gap-1.5 sm:gap-2 text-[11px] sm:text-xs text-gray-400 mt-0.5 flex-wrap">
              {show.year && <span>{show.year}</span>}
              {show.year && <span>•</span>}
              {show.status && (
                <>
                  <span
                    className={`inline-flex items-center gap-1 font-medium px-1.5 py-0.5 rounded text-[10px] sm:text-[11px] ${
                      show.status.toLowerCase() !== 'ended' && show.status.toLowerCase() !== 'canceled' && show.status.toLowerCase() !== 'cancelled'
                        ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                        : 'bg-gray-800 text-gray-400 border border-gray-700/80'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        show.status.toLowerCase() !== 'ended' && show.status.toLowerCase() !== 'canceled' && show.status.toLowerCase() !== 'cancelled'
                          ? 'bg-cyan-400'
                          : 'bg-gray-500'
                      }`}
                    />
                    {show.status === 'Returning Series' ? 'Continuing' : show.status}
                  </span>
                  <span>•</span>
                </>
              )}
              {show.tmdb_id ? (
                <div className="flex items-center gap-1 bg-dark-800 border border-gray-700/80 px-1.5 py-0.5 rounded text-[10px] sm:text-[11px]">
                  <a
                    href={`https://www.themoviedb.org/tv/${show.tmdb_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-300 hover:text-brand-400 flex items-center gap-1 transition"
                    title="View show on TMDb"
                  >
                    <span>TMDb: {show.tmdb_id}</span>
                    <ExternalLink className="w-2.5 h-2.5 text-gray-500" />
                  </a>
                  <button
                    type="button"
                    onClick={onOpenTmdbModal}
                    className="text-gray-400 hover:text-white transition p-0.5 hover:bg-dark-700 rounded ml-0.5"
                    title="Edit or Change TMDb Match"
                  >
                    <Edit2 className="w-2.5 h-2.5" />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={onOpenTmdbModal}
                  className="inline-flex items-center gap-1 text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 px-2 py-0.5 rounded text-[10px] sm:text-[11px] font-semibold transition"
                  title="Find and link this show to TMDb"
                >
                  <AlertTriangle className="w-3 h-3" />
                  Link TMDb
                </button>
              )}

              {show.tvdb_id && (
                <div className="flex items-center gap-1 bg-dark-800 border border-emerald-900/60 px-1.5 py-0.5 rounded text-[10px] sm:text-[11px]">
                  <a
                    href={`https://thetvdb.com/dereferrer/series/${show.tvdb_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition font-medium"
                    title="View show on TheTVDB"
                  >
                    <span>TVDB: {show.tvdb_id}</span>
                    <ExternalLink className="w-2.5 h-2.5 text-emerald-500" />
                  </a>
                </div>
              )}

              <span className="text-gray-600 hidden xs:inline">•</span>
              <button
                type="button"
                onClick={onOpenFixMatchModal}
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
        {/* Scope Toggle: All vs Missing vs This Ep */}
        <div className="flex items-center bg-dark-800 border border-gray-700 rounded-lg p-0.5 text-xs shrink-0">
          <button
            type="button"
            onClick={() => onToggleScope('all')}
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
            onClick={() => onToggleScope('missing')}
            className={`px-2 sm:px-2.5 py-1 rounded-md text-[11px] sm:text-xs font-medium transition ${
              updateScope === 'missing'
                ? 'bg-brand-500 text-dark-950 font-bold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
            title="Only generate/download cards for episodes that are missing title cards"
          >
            Missing Only
          </button>
          <button
            type="button"
            onClick={() => onToggleScope('current')}
            className={`px-2 sm:px-2.5 py-1 rounded-md text-[11px] sm:text-xs font-medium transition ${
              updateScope === 'current'
                ? 'bg-brand-500 text-dark-950 font-bold shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
            title={currentEp ? `Update only S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')}` : 'Update only this episode'}
          >
            This Ep
          </button>
        </div>

        {/* If TEST_MODE is active, allow user to toggle Force Live */}
        {testMode && (
          <label className="flex items-center gap-1 text-[11px] sm:text-xs text-amber-400 cursor-pointer bg-amber-500/10 border border-amber-500/30 px-2 py-1 rounded-lg hover:bg-amber-500/15 transition select-none shrink-0">
            <input
              type="checkbox"
              checked={isForceLive}
              onChange={(e) => onToggleForceLive(e.target.checked)}
              className="accent-amber-500 rounded"
            />
            <span>Live Upload</span>
          </label>
        )}

        {/* Action Button: Apply Cards to Plex */}
        <div className="flex flex-col gap-1 w-full md:w-auto">
          <button
            type="button"
            onClick={onApplyCards}
            disabled={isApplying}
            className={`font-bold px-3 sm:px-4 py-1.5 rounded-lg text-xs sm:text-sm transition flex items-center justify-center gap-1.5 shadow-lg ${
              testMode && !isForceLive
                ? 'bg-amber-500 hover:bg-amber-400 text-dark-950'
                : 'bg-brand-500 hover:bg-brand-400 text-dark-950 shadow-brand-500/20'
            } disabled:opacity-50`}
            title={
              testMode && !isForceLive
                ? 'Simulate title card generation locally (Test Mode)'
                : 'Upload cards and posters directly to Plex'
            }
          >
            {isApplying ? (
              <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            ) : testMode && !isForceLive ? (
              <Sparkles className="w-4 h-4 shrink-0" />
            ) : (
              <Send className="w-4 h-4 shrink-0" />
            )}
            <span className="truncate">
              {isApplying
                ? applyProgress && applyProgress.total > 0
                  ? `${testMode && !isForceLive ? 'Sim' : 'Updating'} ${applyProgress.current}/${applyProgress.total}`
                  : 'Updating...'
                : testMode && !isForceLive
                ? `Simulate (${updateScope === 'all' ? 'All' : updateScope === 'missing' ? 'Missing' : currentEp ? `S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')}` : 'This Ep'})`
                : `Update Plex (${updateScope === 'all' ? 'All' : updateScope === 'missing' ? 'Missing' : currentEp ? `S${String(currentEp.season_number).padStart(2, '0')}E${String(currentEp.episode_number).padStart(2, '0')}` : 'This Ep'})`}
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
  );
};
