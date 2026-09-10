import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, Info, X, FlaskConical, AlertTriangle } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastOptions {
  type?: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastItem extends ToastOptions {
  id: string;
}

interface ToastContextValue {
  showToast: (options: ToastOptions | string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (options: ToastOptions | string) => {
      const opts: ToastOptions =
        typeof options === 'string' ? { message: options, type: 'info' } : options;
      const id = Math.random().toString(36).substring(2, 9);
      const toastItem: ToastItem = {
        ...opts,
        id,
        type: opts.type || 'info',
        duration: opts.duration || 4000
      };

      setToasts((prev) => [...prev, toastItem]);

      if (toastItem.duration && toastItem.duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, toastItem.duration);
      }
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast Overlay Container */}
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0">
        {toasts.map((toast) => {
          const isSuccess = toast.type === 'success';
          const isError = toast.type === 'error';
          const isWarning = toast.type === 'warning';
          const isInfo = toast.type === 'info';

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto rounded-xl p-3.5 shadow-2xl border backdrop-blur-md transition-all duration-300 transform translate-y-0 opacity-100 flex items-start gap-3 bg-dark-900/95 ${
                isSuccess
                  ? 'border-emerald-500/40 text-emerald-200'
                  : isError
                  ? 'border-rose-500/40 text-rose-200'
                  : isWarning
                  ? 'border-amber-500/40 text-amber-200'
                  : 'border-brand-500/40 text-brand-200'
              }`}
            >
              <div className="shrink-0 mt-0.5">
                {isSuccess && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                {isError && <AlertCircle className="w-5 h-5 text-rose-400" />}
                {isWarning && <AlertTriangle className="w-5 h-5 text-amber-400" />}
                {isInfo && (
                  toast.title?.includes('Test') ? (
                    <FlaskConical className="w-5 h-5 text-purple-400" />
                  ) : (
                    <Info className="w-5 h-5 text-brand-400" />
                  )
                )}
              </div>

              <div className="flex-1 min-w-0">
                {toast.title && (
                  <h4 className="text-xs font-semibold text-white tracking-wide mb-0.5">
                    {toast.title}
                  </h4>
                )}
                <p className="text-xs text-gray-300 leading-relaxed break-words whitespace-pre-line">
                  {toast.message}
                </p>
              </div>

              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                className="shrink-0 text-gray-500 hover:text-white transition p-0.5 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
