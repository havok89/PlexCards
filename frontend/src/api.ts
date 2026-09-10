import { Show, Episode, StyleConfig, MediuxSet, AppConfig } from './types';

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
    tmdb_info?: any;
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

  async applyCards(ratingKey: string): Promise<{
    status: string;
    test_mode?: boolean;
    updated_cards: number;
    message: string;
  }> {
    const res = await fetch(`/api/shows/${ratingKey}/apply`, { method: 'POST' });
    return res.json();
  },

  async askAi(ratingKey: string, prompt: string): Promise<any> {
    const res = await fetch(`/api/shows/${ratingKey}/ai-style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });
    return res.json();
  }
};
