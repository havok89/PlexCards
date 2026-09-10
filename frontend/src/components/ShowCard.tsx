import React from 'react';
import { Show } from '../types';
import { Zap, Wand2, Ban, ChevronRight } from 'lucide-react';

interface ShowCardProps {
  show: Show;
  onClick: () => void;
}

export const ShowCard: React.FC<ShowCardProps> = ({ show, onClick }) => {
  return (
    <div
      onClick={onClick}
      className="group bg-dark-900 border border-gray-800 hover:border-brand-500/60 rounded-xl overflow-hidden cursor-pointer transition transform hover:-translate-y-1 shadow-lg hover:shadow-brand-500/10 flex flex-col"
    >
      <div className="relative aspect-[2/3] bg-dark-850 overflow-hidden">
        <img
          src={show.poster_url || 'https://via.placeholder.com/300x450?text=No+Poster'}
          alt={show.title}
          className="w-full h-full object-cover transition duration-300 group-hover:scale-105"
          loading="lazy"
        />

        {/* Mode Pill Badge */}
        <div className="absolute top-2 left-2">
          {show.mode === 'auto' && (
            <span className="bg-emerald-950/80 backdrop-blur-md text-emerald-400 border border-emerald-500/40 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
              <Zap className="w-2.5 h-2.5" /> Auto
            </span>
          )}
          {show.mode === 'generator_only' && (
            <span className="bg-purple-950/80 backdrop-blur-md text-purple-300 border border-purple-500/40 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
              <Wand2 className="w-2.5 h-2.5" /> Preset
            </span>
          )}
          {show.mode === 'ignored' && (
            <span className="bg-gray-900/80 backdrop-blur-md text-gray-400 border border-gray-700 text-[10px] font-bold px-2 py-0.5 rounded-full shadow flex items-center gap-1">
              <Ban className="w-2.5 h-2.5" /> Ignored
            </span>
          )}
        </div>

        {/* Season & Episode Badge */}
        <div className="absolute bottom-2 right-2 bg-black/70 backdrop-blur-md text-gray-200 text-[11px] font-medium px-2 py-0.5 rounded">
          {show.total_seasons}S • {show.total_episodes}E
        </div>
      </div>

      <div className="p-3 flex-1 flex flex-col justify-between">
        <div>
          <h3 className="font-semibold text-sm text-white truncate group-hover:text-brand-500 transition">
            {show.title}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {show.year || `TMDb: ${show.tmdb_id}`}
          </p>
        </div>

        <div className="mt-2.5 pt-2 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-gray-400">
          <span>
            {(show.mediux_cards_count || 0) > 0
              ? `${show.mediux_cards_count} MediUX cards`
              : 'Click to style'}
          </span>
          <ChevronRight className="w-3.5 h-3.5 text-gray-600 group-hover:text-brand-500 transition" />
        </div>
      </div>
    </div>
  );
};
