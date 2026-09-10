import React from 'react';
import { FlaskConical } from 'lucide-react';

interface FilterBarProps {
  filterMode: string;
  onFilterChange: (mode: string) => void;
  totalCount: number;
  testMode: boolean;
  tvLibrary: string;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  filterMode,
  onFilterChange,
  totalCount,
  testMode,
  tvLibrary
}) => {
  return (
    <div className="bg-dark-900/60 border-b border-gray-800/80 px-3 sm:px-6 py-2 sm:py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-2 sm:gap-3">
        {/* Mode Filter Pills */}
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          <button
            onClick={() => onFilterChange('all')}
            className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-md text-[11px] sm:text-xs font-medium border transition ${
              filterMode === 'all'
                ? 'bg-dark-800 text-white border-brand-500'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            All ({totalCount})
          </button>
          <button
            onClick={() => onFilterChange('auto')}
            className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-md text-[11px] sm:text-xs font-medium border transition flex items-center gap-1 sm:gap-1.5 ${
              filterMode === 'auto'
                ? 'bg-dark-800 text-white border-emerald-500'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-emerald-500 shrink-0"></span>
            <span>Auto</span>
          </button>
          <button
            onClick={() => onFilterChange('generator_only')}
            className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-md text-[11px] sm:text-xs font-medium border transition flex items-center gap-1 sm:gap-1.5 ${
              filterMode === 'generator_only'
                ? 'bg-dark-800 text-white border-purple-500'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-purple-500 shrink-0"></span>
            <span>Preset</span>
          </button>
          <button
            onClick={() => onFilterChange('ignored')}
            className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-md text-[11px] sm:text-xs font-medium border transition flex items-center gap-1 sm:gap-1.5 ${
              filterMode === 'ignored'
                ? 'bg-dark-800 text-white border-gray-600'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-gray-500 shrink-0"></span>
            <span>Ignored</span>
          </button>
        </div>

        {/* Status / Test Mode Badge */}
        <div className="text-[11px] sm:text-xs text-gray-400 flex items-center gap-2 sm:gap-4 flex-wrap">
          {testMode && (
            <span className="px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40 font-bold flex items-center gap-1 sm:gap-1.5 shadow-sm">
              <FlaskConical className="w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" />
              <span className="hidden sm:inline">TEST MODE ACTIVE: Plex Uploads Gated</span>
              <span className="sm:hidden">Test Mode (Safe)</span>
            </span>
          )}
          <span className="hidden xs:inline text-gray-500">
            Plex Library: <strong className="text-gray-300">{tvLibrary || 'TV shows'}</strong>
          </span>
        </div>
      </div>
    </div>
  );
};
