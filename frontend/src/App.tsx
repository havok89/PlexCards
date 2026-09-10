import React, { useState, useEffect, useMemo } from 'react';
import { Show, AppConfig } from './types';
import { api } from './api';
import { Navbar } from './components/Navbar';
import { FilterBar } from './components/FilterBar';
import { ShowCard } from './components/ShowCard';
import { ShowStudioModal } from './components/ShowStudioModal';
import { SettingsModal } from './components/SettingsModal';
import { useToast } from './context/ToastContext';
import { Tv, Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  const [shows, setShows] = useState<Show[]>([]);
  const [config, setConfig] = useState<AppConfig>({
    test_mode: true,
    tv_library: 'TV shows',
    poll_interval_hours: 12
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterMode, setFilterMode] = useState<string>('all');
  const [selectedShow, setSelectedShow] = useState<Show | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  const loadData = async () => {
    try {
      const [conf, showsList] = await Promise.all([
        api.getConfig(),
        api.getShows()
      ]);
      setConfig(conf);
      setShows(showsList);
    } catch (e) {
      console.error('Failed to load data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const { showToast } = useToast();

  const handleScan = async () => {
    setIsScanning(true);
    try {
      const res = await api.scanLibrary();
      showToast({
        type: 'success',
        title: 'Scan Complete',
        message: `Indexed ${res.indexed_shows} TV shows from your Plex server.`
      });
      await loadData();
    } catch (e) {
      showToast({
        type: 'error',
        title: 'Scan Failed',
        message: String(e)
      });
    } finally {
      setIsScanning(false);
    }
  };

  const filteredShows = useMemo(() => {
    return shows.filter((s) => {
      const matchesSearch = s.title.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesFilter = filterMode === 'all' || s.mode === filterMode;
      return matchesSearch && matchesFilter;
    });
  }, [shows, searchQuery, filterMode]);

  return (
    <div className="min-h-screen flex flex-col bg-dark-950 text-gray-200">
      <Navbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onScan={handleScan}
        isScanning={isScanning}
        onOpenSettings={() => setIsSettingsOpen(true)}
        listenerConnected={config.listener_connected}
      />

      <FilterBar
        filterMode={filterMode}
        onFilterChange={setFilterMode}
        totalCount={shows.length}
        testMode={config.test_mode}
        tvLibrary={config.tv_library}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {loading ? (
          <div className="text-center py-24 text-gray-500 flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
            <p>Loading your Plex library...</p>
          </div>
        ) : filteredShows.length === 0 ? (
          <div className="text-center py-20 bg-dark-900 border border-gray-800 rounded-xl max-w-md mx-auto p-8">
            <Tv className="w-12 h-12 text-gray-600 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-white">No shows found</h3>
            <p className="text-sm text-gray-400 mt-1 mb-4">
              {shows.length === 0
                ? 'Scan your Plex library to index your TV shows.'
                : 'No shows match your current search or filter.'}
            </p>
            {shows.length === 0 && (
              <button
                onClick={handleScan}
                className="bg-brand-500 text-dark-950 font-bold px-4 py-2 rounded-lg text-sm transition hover:bg-brand-600"
              >
                Scan Plex Now
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-5">
            {filteredShows.map((show) => (
              <ShowCard
                key={show.rating_key}
                show={show}
                onClick={() => setSelectedShow(show)}
              />
            ))}
          </div>
        )}
      </main>

      {selectedShow && (
        <ShowStudioModal
          show={selectedShow}
          testMode={config.test_mode}
          onClose={() => setSelectedShow(null)}
          onShowUpdated={loadData}
        />
      )}

      {isSettingsOpen && (
        <SettingsModal
          onClose={() => setIsSettingsOpen(false)}
          onShowsUpdated={loadData}
          testMode={config.test_mode}
          tvLibrary={config.tv_library}
          listenerConnected={config.listener_connected}
        />
      )}
    </div>
  );
};
