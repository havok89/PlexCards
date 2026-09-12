import React from 'react';
import { MovieCollection } from '../types';
import { Layers, Film } from 'lucide-react';
import { LazyImage } from './LazyImage';

interface CollectionCardProps {
  collection: MovieCollection;
  onClick: () => void;
}

export const CollectionCard: React.FC<CollectionCardProps> = ({ collection, onClick }) => {
  return (
    <div
      onClick={onClick}
      className="group bg-dark-900 border border-gray-800 hover:border-brand-500/60 rounded-xl overflow-hidden cursor-pointer transition transform hover:-translate-y-1 shadow-lg hover:shadow-brand-500/10 flex flex-col"
    >
      <div className="relative aspect-[2/3] bg-dark-850 overflow-hidden">
        {collection.poster_url ? (
          <LazyImage
            src={collection.poster_url}
            alt={collection.title}
            className="w-full h-full object-cover transition duration-300 group-hover:scale-105"
            placeholder={
              <div className="flex flex-col items-center justify-center text-gray-600 p-2">
                <Layers className="w-10 h-10 text-brand-500/40 animate-pulse" />
              </div>
            }
            fallbackIcon={
              <Layers className="w-10 h-10 text-brand-500/70 mb-2 group-hover:text-brand-400 transition" />
            }
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-dark-800 to-dark-900 p-4 text-center border border-gray-800/60">
            <Layers className="w-10 h-10 text-brand-500/70 mb-2 group-hover:text-brand-400 transition" />
            <span className="text-xs font-semibold text-gray-300 line-clamp-2 px-1">{collection.title}</span>
          </div>
        )}

        {/* Movie Count Badge */}
        <div className="absolute top-2 right-2">
          <span className="bg-brand-950/85 backdrop-blur-md text-brand-400 border border-brand-500/40 text-[9px] sm:text-[10px] font-bold px-1.5 sm:px-2 py-0.5 rounded-full flex items-center gap-1 shadow">
            <Film className="w-2.5 h-2.5" />
            {collection.movie_count} {collection.movie_count === 1 ? 'Film' : 'Films'}
          </span>
        </div>

        {/* Franchise Boxset Overlay tag */}
        <div className="absolute bottom-2 left-2 bg-black/75 backdrop-blur-md text-gray-200 text-[10px] font-semibold px-2 py-0.5 rounded flex items-center gap-1 border border-white/10">
          <Layers className="w-2.5 h-2.5 text-brand-400" />
          Franchise Set
        </div>
      </div>

      <div className="p-3 flex-1 flex flex-col justify-between">
        <div>
          <h3 className="font-semibold text-sm text-white truncate group-hover:text-brand-500 transition" title={collection.title}>
            {collection.title}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1.5">
            <span>{collection.movie_count} movies grouped</span>
          </p>
        </div>

        <div className="mt-2.5 pt-2 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-brand-400/90 font-medium">
          <span>Click to style franchise</span>
        </div>
      </div>
    </div>
  );
};
