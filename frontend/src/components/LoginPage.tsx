import React, { useState, useEffect, useRef } from 'react';
import { Film, LogIn, AlertCircle, Loader2, ExternalLink } from 'lucide-react';
import { api } from '../api';
import { AuthUser } from '../types';

interface LoginPageProps {
  onSuccess: (user: AuthUser) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, []);

  const handlePlexSignIn = async () => {
    setError(null);
    setLoading(true);
    setStatusMessage('Connecting to Plex...');
    stopPolling();

    try {
      const pinData = await api.createAuthPin();
      setAuthUrl(pinData.auth_url);

      // Open Plex OAuth window
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2.5;
      const popup = window.open(
        pinData.auth_url,
        'PlexAuthPopup',
        `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
      );

      setStatusMessage('Waiting for Plex sign-in...');

      // Start polling backend for pin completion
      const pinId = pinData.pin_id;
      let attempts = 0;
      const maxAttempts = 120; // 3 minutes maximum

      pollIntervalRef.current = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
          stopPolling();
          setLoading(false);
          setStatusMessage(null);
          setError('Authentication timed out. Please try signing in again.');
          return;
        }

        try {
          const res = await api.pollAuthPin(pinId);
          if (res.status === 'authenticated') {
            stopPolling();
            setLoading(false);
            setStatusMessage(null);
            if (popup && !popup.closed) {
              popup.close();
            }
            if (res.user) {
              onSuccess(res.user);
            } else {
              // Fallback fetch auth status
              const status = await api.getAuthStatus();
              if (status.user) {
                onSuccess(status.user);
              }
            }
          } else if (res.status === 'denied') {
            stopPolling();
            setLoading(false);
            setStatusMessage(null);
            if (popup && !popup.closed) {
              popup.close();
            }
            setError(res.detail || 'Access denied: You do not have permission to manage this Plex server.');
          }
        } catch (err: any) {
          console.error('Poll error:', err);
        }
      }, 1500);

    } catch (err: any) {
      stopPolling();
      setLoading(false);
      setStatusMessage(null);
      setError(err.message || 'Failed to initialize Plex sign in. Please verify your connection.');
    }
  };

  const handleCancel = () => {
    stopPolling();
    setLoading(false);
    setStatusMessage(null);
    setAuthUrl(null);
  };

  return (
    <div className="min-h-screen bg-dark-950 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md bg-dark-900 border border-gray-800 rounded-2xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        {/* Subtle decorative glow */}
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-[#e5a00d]/10 rounded-full blur-3xl pointer-events-none" />

        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-brand-500 flex items-center justify-center text-dark-950 font-black shadow-xl shadow-brand-500/25 mb-4">
            <Film className="w-8 h-8" />
          </div>
          <div className="flex items-center justify-center gap-2">
            <h1 className="text-2xl font-black text-white tracking-tight">PlexCards</h1>
            <span className="text-xs font-mono font-medium px-2 py-0.5 rounded bg-dark-800 border border-gray-700 text-gray-400">
              v0.8
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1.5">
            Automated MediUX & Smart Title Card Generator
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs sm:text-sm flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-400" />
            <div className="flex-1">
              <span className="font-semibold block mb-0.5">Authentication Failed</span>
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Sign In Actions */}
        {!loading ? (
          <div className="space-y-4">
            <p className="text-xs sm:text-sm text-gray-400 text-center leading-relaxed mb-6">
              Authentication is required to view and manage media title cards. Please sign in with your Plex Media Server account.
            </p>
            <button
              onClick={handlePlexSignIn}
              className="w-full bg-[#e5a00d] hover:bg-[#d4940c] text-dark-950 font-bold py-3.5 px-4 rounded-xl flex items-center justify-center gap-2.5 transition shadow-lg shadow-[#e5a00d]/20 hover:scale-[1.01] active:scale-[0.99]"
            >
              <LogIn className="w-5 h-5" />
              <span>Sign in with Plex</span>
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center text-center py-4 space-y-4">
            <div className="relative">
              <Loader2 className="w-10 h-10 text-[#e5a00d] animate-spin" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-white">{statusMessage || 'Signing in...'}</p>
              <p className="text-xs text-gray-400">
                Complete the authorization dialog in the opened window.
              </p>
            </div>

            {authUrl && (
              <a
                href={authUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1 mt-1 underline"
              >
                <span>Popup blocked? Click here to sign in</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}

            <button
              onClick={handleCancel}
              className="mt-4 text-xs font-medium text-gray-400 hover:text-white px-4 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 border border-gray-700 transition"
            >
              Cancel
            </button>
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-gray-800/80 text-center">
          <p className="text-[11px] text-gray-500">
            Secure server access verified through Plex.tv OAuth
          </p>
        </div>
      </div>
    </div>
  );
};
