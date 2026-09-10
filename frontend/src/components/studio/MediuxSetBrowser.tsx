import React from 'react';
import { MediuxSet } from '../../types';
import {
  Zap, Wand2, Ban, Loader2, RotateCcw, Star, Check, ExternalLink
} from 'lucide-react';

interface MediuxSetBrowserProps {
  mode: 'auto' | 'generator_only' | 'mediux_locked' | 'ignored';
  onModeChange: (mode: 'auto' | 'generator_only' | 'ignored') => void;
  isSetsLoading: boolean;
  sortedSets: MediuxSet[];
  activeMediuxSetUrl?: string;
  selectedSetId: string | null;
  preferredCreators: string[];
  onSelectSet: (set: MediuxSet | null) => void;
  onTogglePreferredCreator: (creator: string) => void;
}

export const MediuxSetBrowser: React.FC<MediuxSetBrowserProps> = ({
  mode,
  onModeChange,
  isSetsLoading,
  sortedSets,
  activeMediuxSetUrl,
  selectedSetId,
  preferredCreators,
  onSelectSet,
  onTogglePreferredCreator
}) => {
  return (
    <div className="space-y-4">
      {/* Mode Switcher */}
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider text-gray-400 block mb-2">
          Card Source Mode
        </label>
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => onModeChange('auto')}
            className={`border rounded-lg p-2 text-center text-xs font-medium transition ${
              mode === 'auto'
                ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                : 'bg-dark-800 border-gray-700 text-gray-400 hover:text-white'
            }`}
          >
            <Zap className="w-4 h-4 mx-auto mb-1" />
            Auto (MediUX)
          </button>

          <button
            type="button"
            onClick={() => onModeChange('generator_only')}
            className={`border rounded-lg p-2 text-center text-xs font-medium transition ${
              mode === 'generator_only'
                ? 'bg-purple-500/20 border-purple-500 text-purple-300'
                : 'bg-dark-800 border-gray-700 text-gray-400 hover:text-white'
            }`}
          >
            <Wand2 className="w-4 h-4 mx-auto mb-1" />
            Generator Only
          </button>

          <button
            type="button"
            onClick={() => onModeChange('ignored')}
            className={`border rounded-lg p-2 text-center text-xs font-medium transition ${
              mode === 'ignored'
                ? 'bg-gray-700 border-gray-500 text-white'
                : 'bg-dark-800 border-gray-700 text-gray-400 hover:text-white'
            }`}
          >
            <Ban className="w-4 h-4 mx-auto mb-1" />
            Ignored
          </button>
        </div>

        {mode === 'auto' && (
          <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">
            Checks MediUX for sets that cover your seasons. Automatically fills missing or newly aired episodes with the generator and updates once uploaded.
          </p>
        )}
        {mode === 'generator_only' && (
          <p className="text-[11px] text-purple-400/90 mt-2 leading-relaxed">
            Never polls MediUX. Automatically creates cards for every episode using the style preset below.
          </p>
        )}
      </div>

      {/* MediUX Sets (when in Auto mode) */}
      {mode === 'auto' && (
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
            {!isSetsLoading && activeMediuxSetUrl && (
              <button
                type="button"
                onClick={() => onSelectSet(null)}
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
              {sortedSets.map((set) => {
                const isManual = Boolean(
                  activeMediuxSetUrl &&
                  (activeMediuxSetUrl === set.set_url ||
                   (set.id && activeMediuxSetUrl.includes(set.id)))
                );
                const isAutoDefault = !activeMediuxSetUrl && set.id === selectedSetId;
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
                              onTogglePreferredCreator(set.creator);
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
                              onTogglePreferredCreator(set.creator);
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
                          onClick={() => onSelectSet(set)}
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
    </div>
  );
};
