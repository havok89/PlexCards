import React from 'react';
import { Film, Search, RefreshCw, Settings } from 'lucide-react';

interface NavbarProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onScan: () => void;
  isScanning: boolean;
  onOpenSettings: () => void;
  listenerConnected?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  searchQuery,
  onSearchChange,
  onScan,
  isScanning,
  onOpenSettings,
  listenerConnected = false
}) => {
  return (
    <header className="bg-dark-900 border-b border-gray-800 sticky top-0 z-40 px-3 sm:px-6 py-2.5 sm:py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-2 sm:gap-4">
        {/* Logo & Brand Title */}
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-brand-500 flex items-center justify-center text-dark-950 font-black shadow-lg shadow-brand-500/20 shrink-0">
            <Film className="w-4 h-4 sm:w-5 sm:h-5" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base sm:text-xl font-bold tracking-tight text-white flex items-center gap-1.5 sm:gap-2">
              <span>PlexPosters</span>
              <span className="hidden sm:inline-flex text-xs px-1.5 py-0.5 rounded-full bg-brand-500/20 text-brand-500 border border-brand-500/30">
                v1.0
              </span>
            </h1>
            <p className="text-xs text-gray-400 hidden sm:block truncate">Automated MediUX & Smart Title Card Generator</p>
          </div>
        </div>

        {/* Search, Status & Actions */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="relative">
            <Search className="w-3.5 h-3.5 sm:w-4 sm:h-4 absolute left-2.5 sm:left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              placeholder="Search shows..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="bg-dark-800 border border-gray-700 rounded-lg pl-8 sm:pl-9 pr-3 sm:pr-4 py-1.5 sm:py-2 text-xs sm:text-sm focus:outline-none focus:border-brand-500 w-32 sm:w-48 md:w-64 focus:w-40 sm:focus:w-48 md:focus:w-64 text-white placeholder-gray-500 transition-all"
            />
          </div>

          <div
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-800 border border-gray-700 text-xs font-medium text-gray-300 transition shrink-0"
            title={listenerConnected ? "Plex Real-Time Listener: Connected. New episodes are automatically detected via WebSocket." : "Plex Listener: Reconnecting..."}
          >
            <span className={`w-2 h-2 rounded-full ${listenerConnected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse' : 'bg-amber-400'}`} />
            <span className="text-[11px]">{listenerConnected ? 'Live' : 'Offline'}</span>
          </div>

          <button
            onClick={onScan}
            disabled={isScanning}
            className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-semibold px-2.5 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm flex items-center gap-1.5 sm:gap-2 transition shadow-md shadow-brand-500/10 shrink-0"
            title="Scan Plex TV library"
          >
            <RefreshCw className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${isScanning ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{isScanning ? 'Scanning...' : 'Scan Library'}</span>
            <span className="sm:hidden">{isScanning ? '...' : 'Scan'}</span>
          </button>

          <button
            type="button"
            onClick={onOpenSettings}
            className="bg-dark-800 hover:bg-dark-700 border border-gray-700 text-gray-300 hover:text-white p-1.5 sm:p-2 rounded-lg transition shrink-0"
            title="Application Settings"
          >
            <Settings className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
        </div>
      </div>
    </header>
  );
};
