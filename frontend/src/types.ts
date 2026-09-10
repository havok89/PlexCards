export interface Show {
  rating_key: string;
  tmdb_id: number;
  title: string;
  year?: number;
  poster_url?: string;
  backdrop_url?: string;
  total_seasons: number;
  total_episodes: number;
  mode: 'auto' | 'generator_only' | 'mediux_locked' | 'ignored';
  mediux_set_url?: string;
  mediux_cards_count?: number;
  generator_cards_count?: number;

  // Style attributes attached to show
  layout?: string;
  text_position?: 'left_center' | 'left_bottom' | 'center_bottom' | 'right_center' | 'right_bottom';
  font_family?: string;
  font_color?: string;
  subheading_color?: string;
  gradient_side?: 'left' | 'right' | 'bottom';
  gradient_width_pct?: number;
  gradient_opacity_pct?: number;
  show_subheading?: number;
  subheading_format?: string;
  subheading_icon?: string;
  ai_prompt?: string;
  has_custom_style?: number;
}

export interface Episode {
  rating_key: string;
  season_number: number;
  episode_number: number;
  title: string;
  thumb_url?: string;
}

export interface StyleConfig {
  layout: string;
  text_position: 'left_center' | 'left_bottom' | 'center_bottom' | 'right_center' | 'right_bottom';
  font_family: string;
  font_color: string;
  subheading_color: string;
  gradient_side: 'left' | 'right' | 'bottom';
  gradient_width_pct: number;
  gradient_opacity_pct: number;
  show_subheading: number;
  subheading_format: string;
  subheading_icon: string;
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

