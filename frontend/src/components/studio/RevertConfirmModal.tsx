import React from 'react';
import { RotateCcw, Loader2, AlertTriangle } from 'lucide-react';

interface RevertConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  showTitle: string;
  isReverting: boolean;
  episode?: { season_number: number; episode_number: number; title: string } | null;
}

export const RevertConfirmModal: React.FC<RevertConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  showTitle,
  isReverting,
  episode
}) => {
  if (!isOpen) return null;

  const isSingle = !!episode;
  const epTag = episode
    ? `S${String(episode.season_number).padStart(2, '0')}E${String(episode.episode_number).padStart(2, '0')}`
    : '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-dark-900 border border-gray-700 w-full max-w-md rounded-xl sm:rounded-2xl shadow-2xl p-4 sm:p-5 space-y-4 max-h-[92dvh] overflow-y-auto">
        <div className="flex items-start gap-3">
          <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 shrink-0">
            <RotateCcw className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-white text-sm sm:text-base">
              {isSingle ? `Revert ${epTag} Card to Plex Default?` : 'Revert All Cards to Plex Default?'}
            </h3>
            <p className="text-xs text-gray-300 mt-1.5 leading-relaxed">
              {isSingle ? (
                <>
                  This will reset the title card for <strong className="text-white">&ldquo;{showTitle}&rdquo; &bull; {epTag} (&ldquo;{episode.title}&rdquo;)</strong> back to Plex's native auto-generated video frame thumbnail.
                </>
              ) : (
                <>
                  This will reset all episode cards for <strong className="text-white">&ldquo;{showTitle}&rdquo;</strong> back to Plex's native auto-generated video frame thumbnails.
                </>
              )}
            </p>
            <div className="mt-3 text-[11px] text-amber-300/90 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20 leading-relaxed flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <span>
                {isSingle
                  ? 'The uploaded custom card for this episode in Plex will be deleted and its thumbnail lock released. Any custom screencap override will also be cleared.'
                  : 'Uploaded custom cards on Plex will be deleted and thumbnail locks released. You can re-generate or re-apply title cards in PlexCards at any time.'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2.5 pt-2 border-t border-gray-800">
          <button
            type="button"
            onClick={onClose}
            disabled={isReverting}
            className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white hover:bg-dark-800 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isReverting}
            className="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-bold px-4 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition shadow-md shadow-red-900/30"
          >
            {isReverting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Reverting in Plex...</span>
              </>
            ) : (
              <>
                <RotateCcw className="w-3.5 h-3.5" />
                <span>{isSingle ? `Yes, Revert ${epTag} Card` : 'Yes, Revert All Cards'}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
