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
    <div className="bg-dark-900/60 border-b border-gray-800/80 px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onFilterChange('all')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium border transition ${
              filterMode === 'all'
                ? 'bg-dark-800 text-white border-brand-500'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            All Shows ({totalCount})
          </button>
          <button
            onClick={() => onFilterChange('auto')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium border transition flex items-center gap-1.5 ${
              filterMode === 'auto'
                ? 'bg-dark-800 text-white border-emerald-500'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            Auto (MediUX)
          </button>
          <button
            onClick={() => onFilterChange('generator_only')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium border transition flex items-center gap-1.5 ${
              filterMode === 'generator_only'
                ? 'bg-dark-800 text-white border-purple-500'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-purple-500"></span>
            Generator Only
          </button>
          <button
            onClick={() => onFilterChange('ignored')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium border transition flex items-center gap-1.5 ${
              filterMode === 'ignored'
                ? 'bg-dark-800 text-white border-gray-600'
                : 'text-gray-400 hover:text-gray-200 border-transparent'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-gray-500"></span>
            Ignored
          </button>
        </div>

        <div className="text-xs text-gray-400 flex items-center gap-4">
          {testMode && (
            <span className="px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40 font-bold flex items-center gap-1.5 shadow-sm">
              <FlaskConical className="w-3.5 h-3.5" /> TEST MODE ACTIVE: Plex Uploads Gated
            </span>
          )}
          <span>
            Plex Library: <strong className="text-gray-200">{tvLibrary || 'TV shows'}</strong>
          </span>
        </div>
      </div>
    </div>
  );
};
