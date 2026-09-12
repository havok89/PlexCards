import React, { useState } from 'react';
import { Show } from '../types';
import { Zap, Wand2, Ban, ChevronRight, Film, Tv } from 'lucide-react';
import { LazyImage } from './LazyImage';

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
        {show.poster_url ? (
          <LazyImage
            src={show.poster_url}
            alt={show.title}
            className="w-full h-full object-cover transition duration-300 group-hover:scale-105"
            placeholder={
              <div className="flex flex-col items-center justify-center text-gray-600 p-2">
                <Tv className="w-8 h-8 opacity-40 animate-pulse" />
              </div>
            }
            fallbackIcon={
              <Tv className="w-8 h-8 text-gray-600 mb-1 group-hover:text-brand-500 transition" />
            }
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-dark-800 to-dark-900 p-4 text-center border border-gray-800/60">
            <Film className="w-8 h-8 text-gray-600 mb-2 group-hover:text-brand-500 transition" />
            <span className="text-xs font-semibold text-gray-400 line-clamp-2 px-1">{show.title}</span>
            {show.year && <span className="text-[10px] text-gray-500 mt-1">{show.year}</span>}
          </div>
        )}

        {/* Mode Pill Badge */}
        <div className="absolute top-2 left-2">
          {show.mode === 'auto' && (
            <span className="bg-emerald-950/80 backdrop-blur-md text-emerald-400 border border-emerald-500/40 text-[9px] sm:text-[10px] font-bold px-1.5 sm:px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
              <Zap className="w-2.5 h-2.5" /> Auto
            </span>
          )}
          {show.mode === 'generator_only' && (
            <span className="bg-purple-950/80 backdrop-blur-md text-purple-300 border border-purple-500/40 text-[9px] sm:text-[10px] font-bold px-1.5 sm:px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
              <Wand2 className="w-2.5 h-2.5" /> Preset
            </span>
          )}
          {show.mode === 'ignored' && (
            <span className="bg-gray-900/80 backdrop-blur-md text-gray-400 border border-gray-700 text-[9px] sm:text-[10px] font-bold px-1.5 sm:px-2 py-0.5 rounded-full shadow flex items-center gap-1">
              <Ban className="w-2.5 h-2.5" /> Ignored
            </span>
          )}
        </div>

        {/* Status Badge (Continuing / Ended) */}
        {show.status && (
          <div className="absolute top-2 right-2">
            {show.status.toLowerCase() !== 'ended' &&
            show.status.toLowerCase() !== 'canceled' &&
            show.status.toLowerCase() !== 'cancelled' ? (
              <span className="bg-cyan-950/80 backdrop-blur-md text-cyan-300 border border-cyan-500/40 text-[9px] sm:text-[10px] font-semibold px-1.5 sm:px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                Continuing
              </span>
            ) : (
              <span className="bg-black/70 backdrop-blur-md text-gray-400 border border-gray-700/60 text-[9px] sm:text-[10px] font-medium px-1.5 sm:px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
                <span className="w-1.5 h-1.5 rounded-full bg-gray-500" />
                Ended
              </span>
            )}
          </div>
        )}

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
          <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1.5 truncate">
            {show.year && <span>{show.year}</span>}
            {show.year && <span>•</span>}
            {show.tmdb_id ? (
              <span>TMDb: {show.tmdb_id}</span>
            ) : (
              <span className="text-amber-400 font-medium">TMDb: Unmatched</span>
            )}
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
