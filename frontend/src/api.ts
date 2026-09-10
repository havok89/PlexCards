import { Show, Episode, StyleConfig, MediuxSet, AppConfig, AuthStatus, PinResponse, PollResponse } from './types';

export const api = {
  async getConfig(): Promise<AppConfig> {
    const res = await fetch('/api/config');
    return res.json();
  },

  async getFonts(): Promise<{ name: string; type: string; filename: string }[]> {
    const res = await fetch('/api/fonts');
    const data = await res.json();
    return data.fonts || [];
  },

  async uploadFont(file: File): Promise<{ status: string; font_name: string }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/fonts/upload', {
      method: 'POST',
      body: formData
    });
    return res.json();
  },

  async getShows(): Promise<Show[]> {
    const res = await fetch('/api/shows');
    const data = await res.json();
    return data.shows || [];
  },

  async scanLibrary(): Promise<{ indexed_shows: number }> {
    const res = await fetch('/api/library/scan', { method: 'POST' });
    return res.json();
  },

  async getShowDetails(ratingKey: string): Promise<{
    show: Show;
    episodes: Episode[];
    available_sets: MediuxSet[];
    auto_mediux_set_id?: string | null;
    preferred_creators?: string[];
    tmdb_info?: any;
    initial_ai_generated?: boolean;
    ai_error?: string | null;
  }> {
    const res = await fetch(`/api/shows/${ratingKey}`);
    return res.json();
  },

  async setMode(ratingKey: string, mode: string, mediux_set_url?: string) {
    const res = await fetch(`/api/shows/${ratingKey}/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, mediux_set_url })
    });
    return res.json();
  },

  async saveStyle(ratingKey: string, style: Partial<StyleConfig>) {
    const res = await fetch(`/api/shows/${ratingKey}/style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(style)
    });
    return res.json();
  },

  async getPreviewBlob(ratingKey: string, payload: any): Promise<Blob> {
    const res = await fetch(`/api/shows/${ratingKey}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      throw new Error(`Preview failed with status ${res.status}`);
    }
    return res.blob();
  },

  async applyCards(
    ratingKey: string,
    options?: { force_all?: boolean; force_live?: boolean },
    onProgress?: (progress: { current: number; total: number; label?: string; message?: string }) => void
  ): Promise<{
    status: string;
    test_mode?: boolean;
    force_live?: boolean;
    force_all?: boolean;
    updated_cards: number;
    updated_season_posters?: number;
    message: string;
  }> {
    const res = await fetch(`/api/shows/${ratingKey}/apply-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options || {})
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText || 'Failed to apply cards');
    }

    const reader = res.body?.getReader();
    if (!reader) {
      throw new Error('Streaming not supported in browser');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let finalResult: any = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);
          if (data.type === 'progress' && onProgress) {
            onProgress({
              current: data.current,
              total: data.total,
              label: data.label,
              message: data.message
            });
          } else if (data.type === 'done') {
            finalResult = data.result;
          } else if (data.type === 'error') {
            throw new Error(data.message || 'Error occurred while updating');
          }
        } catch (err) {
          console.error('Error parsing progress line:', err);
        }
      }
    }

    return finalResult || { status: 'success', updated_cards: 0, message: 'Completed' };
  },

  async askAi(ratingKey: string, prompt: string): Promise<any> {
    const res = await fetch(`/api/shows/${ratingKey}/ai-style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Failed to generate style with Gemini' }));
      throw new Error(errData.detail || `AI suggestion failed with status ${res.status}`);
    }
    return res.json();
  },

  async getSettings(): Promise<{ settings: Record<string, string> }> {
    const res = await fetch('/api/settings');
    return res.json();
  },

  async updateSettings(settings: Record<string, any>): Promise<any> {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    return res.json();
  },

  async bulkSetMode(mode: string): Promise<{ status: string; updated_count: number; mode: string }> {
    const res = await fetch('/api/shows/bulk-mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    return res.json();
  },

  async searchTmdb(query: string, year?: number): Promise<{ results: Array<{
    tmdb_id: number;
    name: string;
    year?: number | null;
    overview?: string | null;
    poster_url?: string | null;
    backdrop_url?: string | null;
  }> }> {
    const params = new URLSearchParams({ query });
    if (year) params.append('year', year.toString());
    const res = await fetch(`/api/tmdb/search?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`TMDb search failed: ${res.statusText}`);
    }
    return res.json();
  },

  async setTmdbMatch(ratingKey: string, tmdbId: number): Promise<{
    status: string;
    show: Show;
    tmdb_info?: any;
  }> {
    const res = await fetch(`/api/shows/${ratingKey}/tmdb-match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tmdb_id: tmdbId })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to link TMDb ID' }));
      throw new Error(err.detail || 'Failed to link TMDb ID');
    }
    return res.json();
  },

  async plexFixMatch(ratingKey: string, options?: { title?: string; year?: number }): Promise<{
    success: boolean;
    matched_title?: string;
    matched_year?: number;
    matched_guid?: string;
    message: string;
  }> {
    const res = await fetch(`/api/shows/${ratingKey}/plex-fix-match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options || {})
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fix match in Plex' }));
      throw new Error(err.detail || 'Failed to fix match in Plex');
    }
    return res.json();
  },

  async getAuthStatus(): Promise<AuthStatus> {
    const res = await fetch('/api/auth/status');
    return res.json();
  },

  async createAuthPin(): Promise<PinResponse> {
    const res = await fetch('/api/auth/pin', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create Plex PIN' }));
      throw new Error(err.detail || 'Failed to create Plex PIN');
    }
    return res.json();
  },

  async pollAuthPin(pinId: number): Promise<PollResponse> {
    const res = await fetch(`/api/auth/poll?pin_id=${pinId}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to check Plex auth status' }));
      throw new Error(err.detail || 'Failed to check Plex auth status');
    }
    return res.json();
  },

  async logout(): Promise<{ status: string }> {
    const res = await fetch('/api/auth/logout', { method: 'POST' });
    return res.json();
  }
};

