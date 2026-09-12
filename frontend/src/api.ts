import { Show, Episode, StyleConfig, MediuxSet, AppConfig, AuthStatus, PinResponse, PollResponse, StillsResponse, PaletteResponse, CandidateStill, PlexLibrary } from './types';

export const api = {
  async getConfig(): Promise<AppConfig> {
    const res = await fetch('/api/config');
    return res.json();
  },

  async getLibraries(): Promise<{ libraries: PlexLibrary[]; active_library: string }> {
    const res = await fetch('/api/plex/libraries');
    return res.json();
  },

  async switchLibrary(libraryKey: string): Promise<{ status: string; active_library: string }> {
    const res = await fetch('/api/plex/libraries/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ library_key: libraryKey })
    });
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

  async getShows(library?: string): Promise<Show[]> {
    const url = library ? `/api/shows?library=${encodeURIComponent(library)}` : '/api/shows';
    const res = await fetch(url);
    const data = await res.json();
    return data.shows || [];
  },

  async scanLibrary(library?: string): Promise<{ indexed_shows: number }> {
    const url = library ? `/api/library/scan?library=${encodeURIComponent(library)}` : '/api/library/scan';
    const res = await fetch(url, { method: 'POST' });
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
    has_gemini_key?: boolean;
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
    options?: { force_all?: boolean; force_live?: boolean; source_mode?: string },
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
    let streamError: Error | null = null;

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
            streamError = new Error(data.message || 'Error occurred while updating');
          }
        } catch (err) {
          console.error('Error parsing progress line:', err);
        }
      }
    }

    if (streamError) {
      throw streamError;
    }

    return finalResult || { status: 'success', updated_cards: 0, message: 'Completed' };
  },

  async applyEpisodeCard(
    ratingKey: string,
    seasonNumber: number,
    episodeNumber: number,
    options?: {
      force_live?: boolean;
      source?: 'generator' | 'mediux' | 'auto';
      custom_style?: Partial<StyleConfig>;
    }
  ): Promise<{
    status: string;
    test_mode: boolean;
    force_live: boolean;
    season_number: number;
    episode_number: number;
    title: string;
    source: string;
    message: string;
  }> {
    const res = await fetch(
      `/api/shows/${ratingKey}/episodes/${seasonNumber}/${episodeNumber}/apply`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options || {})
      }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to apply episode card' }));
      throw new Error(err.detail || 'Failed to apply episode card');
    }

    return res.json();
  },

  async getRawStillBlob(ratingKey: string, seasonNumber: number = 1, episodeNumber: number = 1): Promise<Blob> {
    const res = await fetch(`/api/shows/${ratingKey}/raw-still?season_number=${seasonNumber}&episode_number=${episodeNumber}&_t=${Date.now()}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch raw still: status ${res.status}`);
    }
    return res.blob();
  },

  async askAi(ratingKey: string, prompt: string, seasonNumber?: number, episodeNumber?: number): Promise<any> {
    const res = await fetch(`/api/shows/${ratingKey}/ai-style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        season_number: seasonNumber,
        episode_number: episodeNumber
      })
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

  async getDefaultStyle(): Promise<{
    style: StyleConfig;
    sample_show: Show | null;
    sample_episode?: { season_number: number; episode_number: number; title: string } | null;
  }> {
    const res = await fetch('/api/settings/default-style');
    if (!res.ok) {
      throw new Error(`Failed to load default style: status ${res.status}`);
    }
    return res.json();
  },

  async saveDefaultStyle(style: StyleConfig): Promise<{ status: string; style: StyleConfig }> {
    const res = await fetch('/api/settings/default-style', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(style)
    });
    if (!res.ok) {
      throw new Error(`Failed to save default style: status ${res.status}`);
    }
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

  async searchTvdb(query: string, year?: number): Promise<{ results: Array<{
    tvdb_id: number;
    name: string;
    year?: number | null;
    overview?: string | null;
    poster_url?: string | null;
    status?: string | null;
  }> }> {
    const params = new URLSearchParams({ query });
    if (year) params.append('year', year.toString());
    const res = await fetch(`/api/tvdb/search?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`TheTVDB search failed: ${res.statusText}`);
    }
    return res.json();
  },

  async setTvdbMatch(ratingKey: string, tvdbId: number): Promise<{
    status: string;
    show: Show;
    tvdb_info?: any;
    resolved_tmdb_id?: number | null;
  }> {
    const res = await fetch(`/api/shows/${ratingKey}/tvdb-match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tvdb_id: tvdbId })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to link TVDB ID' }));
      throw new Error(err.detail || 'Failed to link TVDB ID');
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
  },

  async getCandidateStills(ratingKey: string, seasonNumber: number, episodeNumber: number): Promise<StillsResponse> {
    const res = await fetch(`/api/shows/${ratingKey}/episodes/${seasonNumber}/${episodeNumber}/stills`);
    if (!res.ok) {
      throw new Error(`Failed to load candidate stills: status ${res.status}`);
    }
    return res.json();
  },

  async selectEpisodeStill(ratingKey: string, seasonNumber: number, episodeNumber: number, stillPath: string): Promise<any> {
    const res = await fetch(`/api/shows/${ratingKey}/episodes/${seasonNumber}/${episodeNumber}/select-still`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ still_path: stillPath })
    });
    if (!res.ok) {
      throw new Error(`Failed to select still: status ${res.status}`);
    }
    return res.json();
  },

  async autoPickStills(ratingKey: string, seasonNumber?: number): Promise<{ status: string; updated_episodes: number; message: string }> {
    const res = await fetch(`/api/shows/${ratingKey}/auto-pick-stills`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(seasonNumber !== undefined ? { season_number: seasonNumber } : {})
    });
    if (!res.ok) {
      throw new Error(`Auto-pick failed: status ${res.status}`);
    }
    return res.json();
  },

  async getStillPalette(ratingKey: string, seasonNumber?: number, episodeNumber?: number): Promise<PaletteResponse> {
    const params = new URLSearchParams();
    if (seasonNumber !== undefined) params.append('season_number', seasonNumber.toString());
    if (episodeNumber !== undefined) params.append('episode_number', episodeNumber.toString());
    const res = await fetch(`/api/shows/${ratingKey}/palette?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Failed to extract palette: status ${res.status}`);
    }
    return res.json();
  },

  async uploadCustomStill(
    ratingKey: string,
    seasonNumber: number,
    episodeNumber: number,
    file: File
  ): Promise<{ status: string; still_path: string; still: CandidateStill }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`/api/shows/${ratingKey}/episodes/${seasonNumber}/${episodeNumber}/custom-still`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      let msg = `Upload failed: status ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) msg = data.detail;
      } catch {
        const text = await res.text();
        if (text) msg = text;
      }
      throw new Error(msg);
    }
    return res.json();
  },

  async deleteCustomStill(
    ratingKey: string,
    seasonNumber: number,
    episodeNumber: number
  ): Promise<{ status: string; message: string }> {
    const res = await fetch(`/api/shows/${ratingKey}/episodes/${seasonNumber}/${episodeNumber}/custom-still`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      let msg = `Failed to delete custom still: status ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) msg = data.detail;
      } catch {
        const text = await res.text();
        if (text) msg = text;
      }
      throw new Error(msg);
    }
    return res.json();
  },

  async downloadShowCardsZip(
    ratingKey: string,
    source: 'auto' | 'mediux' | 'generator' = 'auto'
  ): Promise<Blob> {
    const res = await fetch(`/api/shows/${ratingKey}/export-zip?source=${source}`);
    if (!res.ok) {
      let msg = `Export zip failed: status ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) msg = data.detail;
      } catch {
        const text = await res.text();
        if (text) msg = text;
      }
      throw new Error(msg);
    }
    return res.blob();
  },

  async revertEpisodeCard(
    ratingKey: string,
    seasonNumber: number,
    episodeNumber: number,
    forceLive: boolean = false
  ): Promise<{ status: string; card_source: string; card_url?: string; message: string }> {
    const res = await fetch(`/api/shows/${ratingKey}/episodes/${seasonNumber}/${episodeNumber}/revert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_live: forceLive })
    });
    if (!res.ok) {
      let msg = `Revert card failed: status ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) msg = data.detail;
      } catch {
        const text = await res.text();
        if (text) msg = text;
      }
      throw new Error(msg);
    }
    return res.json();
  },

  async revertShowCards(
    ratingKey: string,
    forceLive: boolean = false
  ): Promise<{ status: string; reverted_count: number; message: string }> {
    const res = await fetch(`/api/shows/${ratingKey}/revert-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_live: forceLive })
    });
    if (!res.ok) {
      let msg = `Revert all cards failed: status ${res.status}`;
      try {
        const data = await res.json();
        if (data.detail) msg = data.detail;
      } catch {
        const text = await res.text();
        if (text) msg = text;
      }
      throw new Error(msg);
    }
    return res.json();
  }
};

