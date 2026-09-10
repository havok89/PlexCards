import React from 'react';
import { Film, X, Search, Loader2 } from 'lucide-react';

export interface TmdbSearchResult {
  tmdb_id: number;
  name: string;
  year?: string;
  overview?: string;
  poster_url?: string;
}

interface TmdbLinkModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeShowTitle: string;
  activeShowTmdbId?: number | null;
  tmdbSearchQuery: string;
  setTmdbSearchQuery: (q: string) => void;
  tmdbSearchYear: string;
  setTmdbSearchYear: (y: string) => void;
  handleSearchTmdb: (q: string, y?: string) => void;
  isSearchingTmdb: boolean;
  customTmdbIdInput: string;
  setCustomTmdbIdInput: (id: string) => void;
  handleLinkTmdb: (tmdbId: number) => void;
  isLinkingTmdb: boolean;
  tmdbSearchResults: TmdbSearchResult[];
}

export const TmdbLinkModal: React.FC<TmdbLinkModalProps> = ({
  isOpen,
  onClose,
  activeShowTitle,
  activeShowTmdbId,
  tmdbSearchQuery,
  setTmdbSearchQuery,
  tmdbSearchYear,
  setTmdbSearchYear,
  handleSearchTmdb,
  isSearchingTmdb,
  customTmdbIdInput,
  setCustomTmdbIdInput,
  handleLinkTmdb,
  isLinkingTmdb,
  tmdbSearchResults
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-dark-900 border border-gray-700 w-full max-w-xl rounded-xl sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92dvh] sm:max-h-[85vh]">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between bg-dark-850">
          <div>
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <Film className="w-4 h-4 text-brand-500" />
              Link TMDb TV Show
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Search TMDb to match &ldquo;{activeShowTitle}&rdquo; or enter a numeric ID directly.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-dark-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 border-b border-gray-800 space-y-3 bg-dark-850/50">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSearchTmdb(tmdbSearchQuery, tmdbSearchYear);
            }}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={tmdbSearchQuery}
                onChange={(e) => setTmdbSearchQuery(e.target.value)}
                placeholder="Search TV show title..."
                className="w-full bg-dark-950 border border-gray-700 text-white rounded-lg pl-9 pr-3 py-1.5 text-xs focus:border-brand-500 focus:outline-none"
              />
            </div>
            <input
              type="text"
              value={tmdbSearchYear}
              onChange={(e) => setTmdbSearchYear(e.target.value)}
              placeholder="Year (opt)"
              className="w-20 bg-dark-950 border border-gray-700 text-white rounded-lg px-2.5 py-1.5 text-xs focus:border-brand-500 focus:outline-none text-center"
            />
            <button
              type="submit"
              disabled={isSearchingTmdb || !tmdbSearchQuery.trim()}
              className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-bold px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition shrink-0"
            >
              {isSearchingTmdb ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              Search
            </button>
          </form>

          <div className="flex items-center gap-2 pt-1 border-t border-gray-800/80">
            <span className="text-[11px] text-gray-400 shrink-0">Direct TMDb ID:</span>
            <input
              type="number"
              value={customTmdbIdInput}
              onChange={(e) => setCustomTmdbIdInput(e.target.value)}
              placeholder="e.g. 95442"
              className="w-32 bg-dark-950 border border-gray-700 text-white rounded-lg px-2 py-1 text-xs focus:border-brand-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => {
                const idNum = parseInt(customTmdbIdInput, 10);
                if (idNum) handleLinkTmdb(idNum);
              }}
              disabled={isLinkingTmdb || !customTmdbIdInput.trim()}
              className="bg-dark-800 hover:bg-dark-700 text-gray-200 border border-gray-700 px-2.5 py-1 rounded-lg text-xs font-medium disabled:opacity-50 transition"
            >
              Link ID
            </button>
          </div>
        </div>

        {/* Search Results List */}
        <div className="p-4 overflow-y-auto flex-1 min-h-0 sm:min-h-[220px] space-y-2.5">
          {isSearchingTmdb ? (
            <div className="flex flex-col items-center justify-center py-10 text-gray-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
              <p className="text-xs">Searching TMDb database...</p>
            </div>
          ) : tmdbSearchResults.length > 0 ? (
            tmdbSearchResults.map((res) => (
              <div
                key={res.tmdb_id}
                className="flex items-center justify-between p-3 rounded-xl bg-dark-800/70 border border-gray-700/80 hover:border-brand-500/50 transition gap-3"
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <div className="w-12 h-16 bg-dark-950 rounded-lg overflow-hidden shrink-0 border border-gray-800">
                    {res.poster_url ? (
                      <img
                        src={res.poster_url}
                        alt={res.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-600 text-[10px]">
                        No Art
                      </div>
                    )}
                  </div>
                  <div className="overflow-hidden">
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-white text-xs truncate">
                        {res.name}
                      </h4>
                      {res.year && (
                        <span className="text-[11px] text-gray-400 bg-dark-900 px-1.5 py-0.5 rounded border border-gray-800">
                          {res.year}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-gray-400 line-clamp-2 mt-0.5">
                      {res.overview || 'No overview available.'}
                    </p>
                    <p className="text-[10px] text-gray-500 mt-0.5">
                      TMDb ID: {res.tmdb_id}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleLinkTmdb(res.tmdb_id)}
                  disabled={isLinkingTmdb}
                  className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-dark-950 font-bold px-3 py-1.5 rounded-lg text-xs shrink-0 transition"
                >
                  {activeShowTmdbId === res.tmdb_id ? 'Active Match' : 'Select & Link'}
                </button>
              </div>
            ))
          ) : (
            <div className="text-center py-10 text-gray-500 text-xs">
              {tmdbSearchQuery ? 'No TV shows found matching this search.' : 'Type a query above to search TMDb.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
