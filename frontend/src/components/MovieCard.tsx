import React, { useState } from 'react';
import { Movie } from '../types';
import { Film, CheckCircle2, Layers, Clock } from 'lucide-react';
import { LazyImage } from './LazyImage';

interface MovieCardProps {
  movie: Movie;
  onClick: () => void;
}

export const MovieCard: React.FC<MovieCardProps> = ({ movie, onClick }) => {
  const formatDuration = (mins?: number) => {
    if (!mins) return null;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  return (
    <div
      onClick={onClick}
      className="group bg-dark-900 border border-gray-800 hover:border-brand-500/60 rounded-xl overflow-hidden cursor-pointer transition transform hover:-translate-y-1 shadow-lg hover:shadow-brand-500/10 flex flex-col"
    >
      <div className="relative aspect-[2/3] bg-dark-850 overflow-hidden">
        {movie.poster_url ? (
          <LazyImage
            src={movie.poster_url}
            alt={movie.title}
            className="w-full h-full object-cover transition duration-300 group-hover:scale-105"
            placeholder={
              <div className="flex flex-col items-center justify-center text-gray-600 p-2">
                <Film className="w-8 h-8 opacity-40 animate-pulse" />
              </div>
            }
            fallbackIcon={
              <Film className="w-8 h-8 text-gray-600 mb-1 group-hover:text-brand-500 transition" />
            }
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-dark-800 to-dark-900 p-4 text-center border border-gray-800/60">
            <Film className="w-8 h-8 text-gray-600 mb-2 group-hover:text-brand-500 transition" />
            <span className="text-xs font-semibold text-gray-400 line-clamp-2 px-1">{movie.title}</span>
            {movie.year && <span className="text-[10px] text-gray-500 mt-1">{movie.year}</span>}
          </div>
        )}

        {/* Custom Poster Indicator Badge */}
        {movie.has_custom_poster === 1 && (
          <div className="absolute top-2 left-2">
            <span className="bg-emerald-950/85 backdrop-blur-md text-emerald-400 border border-emerald-500/40 text-[9px] sm:text-[10px] font-bold px-1.5 sm:px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
              <CheckCircle2 className="w-2.5 h-2.5" /> Custom
            </span>
          </div>
        )}

        {/* Duration Badge */}
        {movie.duration ? (
          <div className="absolute bottom-2 right-2 bg-black/75 backdrop-blur-md text-gray-200 text-[10px] sm:text-[11px] font-medium px-1.5 sm:px-2 py-0.5 rounded flex items-center gap-1">
            <Clock className="w-2.5 h-2.5 text-gray-400" />
            {formatDuration(movie.duration)}
          </div>
        ) : null}
      </div>

      <div className="p-3 flex-1 flex flex-col justify-between">
        <div>
          <h3 className="font-semibold text-sm text-white truncate group-hover:text-brand-500 transition" title={movie.title}>
            {movie.title}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1.5 truncate">
            {movie.year && <span>{movie.year}</span>}
            {movie.year && <span>•</span>}
            {movie.tmdb_id ? (
              <span>TMDb: {movie.tmdb_id}</span>
            ) : (
              <span className="text-amber-400 font-medium">TMDb: Unmatched</span>
            )}
          </p>
        </div>

        {movie.collection_name ? (
          <div className="mt-2.5 pt-2 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-brand-400/90 font-medium truncate">
            <span className="flex items-center gap-1 truncate" title={movie.collection_name}>
              <Layers className="w-3 h-3 shrink-0" />
              <span className="truncate">{movie.collection_name}</span>
            </span>
          </div>
        ) : (
          <div className="mt-2.5 pt-2 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-gray-400">
            <span>Click to change poster</span>
          </div>
        )}
      </div>
    </div>
  );
};
