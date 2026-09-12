import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Search, Check, Upload, ChevronDown, X, Type } from 'lucide-react';
import { FontItem } from '../../types';

interface VisualFontPickerProps {
  label: string;
  selectedFont?: string;
  onSelectFont: (fontName: string) => void;
  availableFonts: FontItem[];
  onUploadFont?: (file: File) => Promise<void>;
  isUploadingFont?: boolean;
  isSubtitle?: boolean;
  matchTitleFontName?: string;
  onResetMatchTitle?: () => void;
}

export const VisualFontPicker: React.FC<VisualFontPickerProps> = ({
  label,
  selectedFont,
  onSelectFont,
  availableFonts,
  onUploadFont,
  isUploadingFont,
  isSubtitle = false,
  matchTitleFontName,
  onResetMatchTitle
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'bundled' | 'custom'>('all');
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadedFontsRef = useRef<Set<string>>(new Set());

  // Dynamically load server fonts into the browser's FontFace set for true typography preview
  useEffect(() => {
    availableFonts.forEach((f) => {
      if (f.filename && !loadedFontsRef.current.has(f.name)) {
        loadedFontsRef.current.add(f.name);
        try {
          const fontFace = new FontFace(f.name, `url(/api/fonts/file/${encodeURIComponent(f.filename)})`);
          fontFace
            .load()
            .then((loaded) => {
              document.fonts.add(loaded);
            })
            .catch(() => {
              // Graceful fallback
            });
        } catch {
          // FontFace API unsupported
        }
      }
    });
  }, [availableFonts]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    }
  }, [isOpen]);

  // Close dropdown on outside click or escape
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const customCount = useMemo(
    () => availableFonts.filter((f) => f.type === 'custom').length,
    [availableFonts]
  );
  const bundledCount = useMemo(
    () => availableFonts.filter((f) => f.type !== 'custom').length,
    [availableFonts]
  );

  const filteredFonts = useMemo(() => {
    return availableFonts.filter((f) => {
      if (filterType === 'custom' && f.type !== 'custom') return false;
      if (filterType === 'bundled' && f.type === 'custom') return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        return f.name.toLowerCase().includes(q);
      }
      return true;
    });
  }, [availableFonts, filterType, searchQuery]);

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onUploadFont) return;
    await onUploadFont(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const isMatchedTitle = isSubtitle && (!selectedFont || selectedFont === matchTitleFontName);
  const displayFontName = isMatchedTitle
    ? `Match Title (${matchTitleFontName || 'Default'})`
    : selectedFont || 'Select Font';

  const selectedFontItem = availableFonts.find(
    (f) => f.name.toLowerCase() === selectedFont?.toLowerCase()
  );

  return (
    <div className="relative" ref={containerRef}>
      {/* Label and optional Quick-Reset */}
      <div className="flex items-center justify-between mb-1">
        <label className="text-[11px] text-gray-400 font-medium flex items-center gap-1.5">
          <Type className="w-3 h-3 text-brand-400" />
          <span>{label}</span>
        </label>
        {isSubtitle && !isMatchedTitle && onResetMatchTitle && (
          <button
            type="button"
            onClick={onResetMatchTitle}
            className="text-[10px] text-brand-400 hover:text-brand-300 hover:underline transition"
          >
            Reset to Match Title
          </button>
        )}
      </div>

      {/* Main Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full bg-dark-800 border text-left px-3 py-2 rounded-lg flex items-center justify-between gap-2 transition group ${
          isOpen
            ? 'border-brand-500 ring-1 ring-brand-500/50'
            : 'border-gray-700 hover:border-gray-600'
        }`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="text-xs font-medium text-white truncate"
            style={{ fontFamily: isMatchedTitle ? matchTitleFontName : selectedFont }}
          >
            {displayFontName}
          </span>

          {selectedFontItem?.type === 'custom' && (
            <span className="shrink-0 text-[9px] font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/40 px-1.5 py-0.2 rounded">
              Custom
            </span>
          )}

          {selectedFont && !selectedFontItem && !isMatchedTitle && (
            <span className="shrink-0 text-[9px] font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 px-1.5 py-0.2 rounded">
              Suggested
            </span>
          )}
        </div>

        <ChevronDown
          className={`w-3.5 h-3.5 text-gray-400 group-hover:text-gray-200 transition-transform duration-200 shrink-0 ${
            isOpen ? 'rotate-180 text-brand-400' : ''
          }`}
        />
      </button>

      {/* Dropdown Popover */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1.5 bg-dark-900 border border-gray-700 rounded-xl shadow-2xl z-50 overflow-hidden flex flex-col max-h-[380px] animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Popover Header: Search & Upload */}
          <div className="p-2 border-b border-gray-800 bg-dark-850 flex flex-col gap-2 shrink-0">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search fonts..."
                className="w-full bg-dark-800 border border-gray-700 rounded-lg pl-8 pr-7 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white p-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {/* Filter Pills & Upload Button */}
            <div className="flex items-center justify-between gap-1 text-[10px]">
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setFilterType('all')}
                  className={`px-2 py-0.5 rounded font-medium transition ${
                    filterType === 'all'
                      ? 'bg-brand-500 text-dark-950 font-bold'
                      : 'bg-dark-800 text-gray-400 hover:text-gray-200'
                  }`}
                >
                  All ({availableFonts.length})
                </button>
                <button
                  type="button"
                  onClick={() => setFilterType('bundled')}
                  className={`px-2 py-0.5 rounded font-medium transition ${
                    filterType === 'bundled'
                      ? 'bg-brand-500 text-dark-950 font-bold'
                      : 'bg-dark-800 text-gray-400 hover:text-gray-200'
                  }`}
                >
                  Bundled ({bundledCount})
                </button>
                {customCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setFilterType('custom')}
                    className={`px-2 py-0.5 rounded font-medium transition ${
                      filterType === 'custom'
                        ? 'bg-purple-500 text-white font-bold'
                        : 'bg-dark-800 text-purple-400 hover:text-purple-300'
                    }`}
                  >
                    Custom ({customCount})
                  </button>
                )}
              </div>

              {onUploadFont && (
                <>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploadingFont}
                    className="flex items-center gap-1 text-brand-400 hover:text-brand-300 transition py-0.5 px-1.5 rounded bg-brand-500/10 hover:bg-brand-500/20 border border-brand-500/30"
                    title="Upload a custom .ttf or .otf font"
                  >
                    <Upload className="w-2.5 h-2.5" />
                    <span>Upload</span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".ttf,.otf"
                    onChange={handleFileInputChange}
                    className="hidden"
                  />
                </>
              )}
            </div>
          </div>

          {/* Font List */}
          <div className="overflow-y-auto p-1.5 space-y-1 divide-y divide-gray-800/40 scrollbar-thin scrollbar-thumb-gray-800">
            {/* Subtitle Match Option */}
            {isSubtitle && (
              <button
                type="button"
                onClick={() => {
                  onSelectFont('');
                  setIsOpen(false);
                }}
                className={`w-full text-left px-2.5 py-2 rounded-lg flex items-center justify-between gap-2 transition ${
                  isMatchedTitle
                    ? 'bg-brand-500/15 text-brand-300 border border-brand-500/30'
                    : 'text-gray-300 hover:bg-dark-800 hover:text-white'
                }`}
              >
                <div className="flex flex-col">
                  <span className="text-xs font-semibold">Match Title Font</span>
                  <span className="text-[10px] text-gray-400">
                    Inherits {matchTitleFontName || 'Primary font'}
                  </span>
                </div>
                {isMatchedTitle && <Check className="w-4 h-4 text-brand-400 shrink-0" />}
              </button>
            )}

            {/* Custom/Suggested Font if not in list */}
            {selectedFont &&
              !availableFonts.some(
                (f) => f.name.toLowerCase() === selectedFont.toLowerCase()
              ) &&
              !isMatchedTitle && (
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="w-full text-left px-2.5 py-2 rounded-lg flex items-center justify-between gap-2 bg-cyan-500/15 text-cyan-300 border border-cyan-500/30"
                >
                  <div className="flex flex-col">
                    <span className="text-xs font-bold" style={{ fontFamily: selectedFont }}>
                      {selectedFont}
                    </span>
                    <span className="text-[10px] text-cyan-400">AI Suggested / Auto-Downloaded</span>
                  </div>
                  <Check className="w-4 h-4 text-cyan-400 shrink-0" />
                </button>
              )}

            {filteredFonts.length === 0 ? (
              <div className="text-center py-6 text-xs text-gray-500">
                No fonts found matching "{searchQuery}"
              </div>
            ) : (
              filteredFonts.map((font) => {
                const isSelected =
                  !isMatchedTitle &&
                  selectedFont?.toLowerCase() === font.name.toLowerCase();

                return (
                  <button
                    key={font.name}
                    type="button"
                    onClick={() => {
                      onSelectFont(font.name);
                      setIsOpen(false);
                    }}
                    className={`w-full text-left px-2.5 py-2 rounded-lg flex items-center justify-between gap-3 transition group ${
                      isSelected
                        ? 'bg-brand-500/15 text-brand-300 border border-brand-500/30'
                        : 'text-gray-300 hover:bg-dark-800 hover:text-white'
                    }`}
                  >
                    {/* Left: Font Name & Type */}
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="text-xs font-medium truncate group-hover:text-white">
                        {font.name}
                      </span>
                      {font.type === 'custom' && (
                        <span className="text-[9px] font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/40 px-1 py-0.2 rounded shrink-0">
                          Custom
                        </span>
                      )}
                    </div>

                    {/* Right: Live Visual Preview Sample */}
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={`text-sm tracking-wide transition truncate max-w-[140px] sm:max-w-[180px] ${
                          isSelected
                            ? 'text-brand-300 font-bold'
                            : 'text-gray-400 group-hover:text-gray-200'
                        }`}
                        style={{ fontFamily: font.name }}
                      >
                        SAMPLE 01
                      </span>
                      {isSelected ? (
                        <Check className="w-4 h-4 text-brand-400 shrink-0" />
                      ) : (
                        <div className="w-4 h-4" />
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
