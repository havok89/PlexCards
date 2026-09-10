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
    <header className="bg-dark-900 border-b border-gray-800 sticky top-0 z-40 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-brand-500 flex items-center justify-center text-dark-950 font-black shadow-lg shadow-brand-500/20">
            <Film className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              PlexPosters
              <span className="text-xs px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-500 border border-brand-500/30">
                v1.0
              </span>
            </h1>
            <p className="text-xs text-gray-400">Automated MediUX & Smart Title Card Generator</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              placeholder="Search TV shows..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="bg-dark-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-brand-500 w-64 text-white placeholder-gray-500 transition"
            />
          </div>

          <div
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-800 border border-gray-700 text-xs font-medium text-gray-300 transition"
            title={listenerConnected ? "Plex Real-Time Listener: Connected. New episodes are automatically detected via WebSocket." : "Plex Listener: Reconnecting..."}
          >
            <span className={`w-2 h-2 rounded-full ${listenerConnected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse' : 'bg-amber-400'}`} />
            <span className="text-[11px]">{listenerConnected ? 'Live' : 'Offline'}</span>
          </div>

          <button
            onClick={onScan}
            disabled={isScanning}
            className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-semibold px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition shadow-md shadow-brand-500/10"
          >
            <RefreshCw className={`w-4 h-4 ${isScanning ? 'animate-spin' : ''}`} />
            <span>{isScanning ? 'Scanning Plex...' : 'Scan Library'}</span>
          </button>

          <button
            type="button"
            onClick={onOpenSettings}
            className="bg-dark-800 hover:bg-dark-700 border border-gray-700 text-gray-300 hover:text-white p-2 rounded-lg transition"
            title="Application Settings"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
};
