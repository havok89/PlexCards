import React from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';

interface PlexFixMatchModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeShowTitle: string;
  handlePlexFixMatch: () => void;
  isFixingPlexMatch: boolean;
}

export const PlexFixMatchModal: React.FC<PlexFixMatchModalProps> = ({
  isOpen,
  onClose,
  activeShowTitle,
  handlePlexFixMatch,
  isFixingPlexMatch
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm">
      <div className="bg-dark-900 border border-gray-700 w-full max-w-md rounded-xl sm:rounded-2xl shadow-2xl p-4 sm:p-5 space-y-4 max-h-[92dvh] overflow-y-auto">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-500/10 border border-blue-500/30 rounded-xl text-blue-400 shrink-0">
            <RefreshCw className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-white text-sm">
              Fix Match in Plex?
            </h3>
            <p className="text-xs text-gray-300 mt-1 leading-relaxed">
              This will instruct Plex Media Server to search its agent for <strong className="text-white">&ldquo;{activeShowTitle}&rdquo;</strong> and apply official metadata (description, cast, genres).
            </p>
            <p className="text-[11px] text-amber-400/90 mt-2 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20 leading-tight">
              ⚠️ <strong>Note:</strong> When Plex matches a show, Plex may download its own default artwork. If needed, you can re-apply your custom cards and posters here at any time.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2.5 pt-2 border-t border-gray-800">
          <button
            type="button"
            onClick={onClose}
            disabled={isFixingPlexMatch}
            className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-white hover:bg-dark-800 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handlePlexFixMatch}
            disabled={isFixingPlexMatch}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold px-4 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition shadow-md"
          >
            {isFixingPlexMatch ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Fixing in Plex...</span>
              </>
            ) : (
              <span>Yes, Fix Match in Plex</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
