export interface Show {
  rating_key: string;
  tmdb_id: number;
  tvdb_id?: number;
  title: string;
  year?: number;
  poster_url?: string;
  backdrop_url?: string;
  total_seasons: number;
  total_episodes: number;
  mode: 'auto' | 'generator_only' | 'mediux_locked' | 'ignored';
  status?: string;
  mediux_set_url?: string;
  mediux_cards_count?: number;
  generator_cards_count?: number;

  // Style attributes attached to show
  layout?: string;
  text_position?: 'left_center' | 'left_bottom' | 'center_bottom' | 'right_center' | 'right_bottom' | 'top_left' | 'top_center' | 'top_right' | 'center' | 'center_right' | 'bottom_center';
  font_family?: string;
  subheading_font_family?: string;
  font_color?: string;
  subheading_color?: string;
  gradient_side?: 'left' | 'right' | 'bottom' | 'top' | 'center';
  gradient_width_pct?: number;
  gradient_opacity_pct?: number;
  show_subheading?: number;
  subheading_format?: string;
  subheading_icon?: string;
  title_font_size?: number;
  subheading_font_size?: number;
  text_box_width_pct?: number;
  subheading_gap?: number;
  subheading_casing?: 'upper' | 'title' | 'lower';
  subheading_position?: 'above' | 'below';
  subheading_tracking?: number;
  frosted_blur_pct?: number;
  film_grain_pct?: number;
  vignette_pct?: number;
  text_shadow_mode?: 'subtle' | 'cinematic' | 'glow' | 'none';
  show_logo?: number;
  logo_position?: 'top_right' | 'top_left' | 'bottom_right' | 'bottom_left';
  logo_opacity_pct?: number;
  logo_monochrome?: number;
  ai_prompt?: string;
  has_custom_style?: number;
  library_section_id?: string;
  library_name?: string;
}

export interface PlexLibrary {
  key: string;
  title: string;
  type: string;
}

export interface Episode {
  rating_key: string;
  season_number: number;
  episode_number: number;
  title: string;
  thumb_url?: string;
  card_source?: string;
  card_url?: string;
}

export interface StyleConfig {
  layout: string;
  text_position: 'left_center' | 'left_bottom' | 'center_bottom' | 'right_center' | 'right_bottom' | 'top_left' | 'top_center' | 'top_right' | 'center' | 'center_right' | 'bottom_center';
  font_family: string;
  subheading_font_family?: string;
  font_color: string;
  subheading_color: string;
  gradient_side: 'left' | 'right' | 'bottom' | 'top' | 'center';
  gradient_width_pct: number;
  gradient_opacity_pct: number;
  show_subheading: number;
  subheading_format: string;
  subheading_icon: string;
  title_font_size: number;
  subheading_font_size: number;
  text_box_width_pct?: number;
  subheading_gap?: number;
  subheading_casing?: 'upper' | 'title' | 'lower';
  subheading_position?: 'above' | 'below';
  subheading_tracking?: number;
  frosted_blur_pct?: number;
  film_grain_pct?: number;
  vignette_pct?: number;
  text_shadow_mode?: 'subtle' | 'cinematic' | 'glow' | 'none';
  show_logo?: number;
  logo_position?: 'top_right' | 'top_left' | 'bottom_right' | 'bottom_left';
  logo_opacity_pct?: number;
  logo_monochrome?: number;
  ai_prompt?: string;
}

export interface MediuxSet {
  id: string;
  set_name: string;
  creator: string;
  date_updated: string;
  set_url: string;
  total_cards: number;
  seasons_covered: number[];
  title_cards: Record<string, string>;
  season_posters?: Record<string, string>;
  poster_url?: string;
}

export interface AppConfig {
  test_mode: boolean;
  tv_library: string;
  poll_interval_hours: number;
  listener_connected?: boolean;
  auth_enabled?: boolean;
  has_gemini_key?: boolean;
  has_tvdb_key?: boolean;
  has_tmdb_key?: boolean;
}

export interface AuthUser {
  username: string;
  email?: string;
  thumb?: string;
}

export interface AuthStatus {
  auth_enabled: boolean;
  authenticated: boolean;
  user: AuthUser | null;
}

export interface PinResponse {
  pin_id: number;
  code: string;
  auth_url: string;
}

export interface PollResponse {
  status: 'pending' | 'authenticated' | 'denied';
  token?: string;
  user?: AuthUser;
  detail?: string;
}

export interface CandidateStill {
  file_path: string;
  thumb_url: string;
  full_url: string;
  width: number;
  height: number;
  aspect_ratio: number;
  is_16_9: boolean;
  vote_average: number;
  vote_count: number;
  quality_score: number;
  is_top_pick?: boolean;
  is_selected?: boolean;
  provider?: 'tvdb' | 'tmdb' | 'custom';
}

export interface FontItem {
  name: string;
  type: string;
  filename?: string;
}

export interface StillsResponse {
  stills: CandidateStill[];
  selected_still_path: string | null;
}

export interface PaletteResponse {
  dominant: string;
  vibrant: string;
  swatches: string[];
  recommended: {
    font_color: string;
    subheading_color: string;
  };
}


