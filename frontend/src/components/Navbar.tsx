import React, { useState, useRef, useEffect } from 'react';
import { Film, Search, RefreshCw, Settings, LogOut, Tv } from 'lucide-react';
import { AuthUser, PlexLibrary } from '../types';

interface NavbarProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onScan: () => void;
  isScanning: boolean;
  onOpenSettings: () => void;
  listenerConnected?: boolean;
  currentUser?: AuthUser | null;
  onLogout?: () => void;
  libraries?: PlexLibrary[];
  activeLibrary?: string;
  onSelectLibrary?: (key: string) => void;
  mediaType: 'shows' | 'movies';
  onMediaTypeChange: (type: 'shows' | 'movies') => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  searchQuery,
  onSearchChange,
  onScan,
  isScanning,
  onOpenSettings,
  listenerConnected = false,
  currentUser,
  onLogout,
  libraries = [],
  activeLibrary = 'all',
  onSelectLibrary,
  mediaType,
  onMediaTypeChange
}) => {
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) {
        setIsProfileMenuOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsProfileMenuOpen(false);
      }
    };

    if (isProfileMenuOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isProfileMenuOpen]);

  const filteredLibraries = libraries.filter(lib =>
    mediaType === 'shows' ? lib.type === 'show' : lib.type === 'movie'
  );

  return (
    <header className="bg-dark-900 border-b border-gray-800 sticky top-0 z-40 px-3 sm:px-6 py-2 sm:py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2 sm:gap-4">
          {/* Logo & Brand Title + Mode Switcher */}
          <div className="flex items-center gap-2 sm:gap-4 shrink-0">
            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-brand-500 flex items-center justify-center text-dark-950 font-black shadow-lg shadow-brand-500/20 shrink-0">
                <Film className="w-4 h-4 sm:w-5 sm:h-5" />
              </div>
              <h1 className="text-base sm:text-lg font-bold tracking-tight text-white hidden md:block">
                PlexCards
              </h1>
            </div>

            {/* Top-Level Mode Toggle: TV Shows | Movies */}
            <div className="flex items-center bg-dark-950 p-0.5 sm:p-1 rounded-xl border border-gray-800 shrink-0">
              <button
                onClick={() => onMediaTypeChange('shows')}
                className={`flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 rounded-lg text-xs font-semibold transition ${
                  mediaType === 'shows'
                    ? 'bg-brand-500 text-dark-950 shadow-md shadow-brand-500/20'
                    : 'text-gray-400 hover:text-white hover:bg-dark-850'
                }`}
              >
                <Tv className="w-3.5 h-3.5" />
                <span><span className="sm:hidden">TV</span><span className="hidden sm:inline">TV Shows</span></span>
              </button>
              <button
                onClick={() => onMediaTypeChange('movies')}
                className={`flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 rounded-lg text-xs font-semibold transition ${
                  mediaType === 'movies'
                    ? 'bg-brand-500 text-dark-950 shadow-md shadow-brand-500/20'
                    : 'text-gray-400 hover:text-white hover:bg-dark-850'
                }`}
              >
                <Film className="w-3.5 h-3.5" />
                <span>Movies</span>
              </button>
            </div>
          </div>

          {/* Search (Desktop only) & Action Buttons */}
          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            {/* Desktop Search Bar */}
            <div className="relative hidden sm:block">
              <Search className="w-3.5 h-3.5 sm:w-4 sm:h-4 absolute left-2.5 sm:left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                placeholder={mediaType === 'shows' ? "Search shows..." : "Search movies..."}
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                className="bg-dark-800 border border-gray-700 rounded-lg pl-8 sm:pl-9 pr-3 sm:pr-4 py-1.5 sm:py-2 text-xs sm:text-sm focus:outline-none focus:border-brand-500 w-36 sm:w-44 md:w-56 text-white placeholder-gray-500 transition-all"
              />
            </div>

            {/* Library Switcher */}
            {filteredLibraries.length > 0 && (
              <div className="hidden md:flex items-center gap-1.5 bg-dark-800 border border-gray-700 rounded-lg px-2 sm:px-2.5 py-1.5 text-xs text-gray-300 shrink-0" title={`Switch Plex ${mediaType === 'shows' ? 'TV' : 'Movie'} Library`}>
                {mediaType === 'shows' ? (
                  <Tv className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                ) : (
                  <Film className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                )}
                <select
                  value={activeLibrary || 'all'}
                  onChange={(e) => onSelectLibrary?.(e.target.value)}
                  className="bg-transparent text-xs text-white focus:outline-none cursor-pointer pr-1 font-medium"
                >
                  <option value="all" className="bg-dark-900 text-white">
                    {mediaType === 'shows' ? 'All TV Libraries' : 'All Movie Libraries'}
                  </option>
                  {filteredLibraries.map((lib) => (
                    <option key={lib.key} value={lib.key} className="bg-dark-900 text-white">
                      {lib.title}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Scan Library Button */}
            <button
              onClick={onScan}
              disabled={isScanning}
              className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-semibold p-1.5 sm:px-4 sm:py-2 rounded-lg text-xs sm:text-sm flex items-center gap-1.5 sm:gap-2 transition shadow-md shadow-brand-500/10 shrink-0"
              title={`Scan Plex ${mediaType === 'shows' ? 'TV' : 'Movie'} library`}
            >
              <RefreshCw className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${isScanning ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">{isScanning ? 'Scanning...' : 'Scan Library'}</span>
            </button>

            {/* Settings Button */}
            <button
              type="button"
              onClick={onOpenSettings}
              className="bg-dark-800 hover:bg-dark-700 border border-gray-700 text-gray-300 hover:text-white p-1.5 sm:p-2 rounded-lg transition shrink-0"
              title="Application Settings"
            >
              <Settings className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>

            {/* Profile Dropdown */}
            {currentUser && (
              <div className="relative shrink-0 pl-1 sm:pl-2 border-l border-gray-800" ref={profileMenuRef}>
                <button
                  type="button"
                  onClick={() => setIsProfileMenuOpen((prev) => !prev)}
                  className="flex items-center p-0.5 rounded-full hover:ring-2 hover:ring-brand-500/50 transition focus:outline-none"
                  title={`Signed in as ${currentUser.username}. Click for options.`}
                >
                  {currentUser.thumb ? (
                    <img
                      src={currentUser.thumb}
                      alt={currentUser.username}
                      className="w-7 h-7 sm:w-8 sm:h-8 rounded-full border border-gray-700 object-cover"
                    />
                  ) : (
                    <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-dark-800 border border-gray-700 flex items-center justify-center text-[10px] sm:text-xs font-bold text-gray-300">
                      {currentUser.username.slice(0, 2).toUpperCase()}
                    </div>
                  )}
                </button>

                {/* Dropdown Menu */}
                {isProfileMenuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-dark-950 border border-gray-800 rounded-xl shadow-2xl py-1.5 z-50 animate-fadeIn">
                    <div className="px-3 py-2 border-b border-gray-800/80">
                      <p className="text-xs font-bold text-white truncate" title={currentUser.username}>
                        {currentUser.username}
                      </p>
                      <p className="text-[10px] text-gray-400">Plex Account</p>
                    </div>

                    {onLogout && (
                      <button
                        type="button"
                        onClick={() => {
                          setIsProfileMenuOpen(false);
                          onLogout();
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-gray-300 hover:text-rose-400 hover:bg-rose-950/30 transition text-left"
                      >
                        <LogOut className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                        <span>Sign Out</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Mobile Search Bar */}
        <div className="sm:hidden relative w-full">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            placeholder={mediaType === 'shows' ? "Search shows..." : "Search movies..."}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-dark-800 border border-gray-700 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-brand-500 transition-all"
          />
        </div>
      </div>
    </header>
  );
};
