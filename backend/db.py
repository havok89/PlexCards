import json
import sqlite3
from typing import Dict, List, Optional, Any
from backend.config import DB_PATH, PLEX_TV_LIBRARY

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Shows table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shows (
        rating_key TEXT PRIMARY KEY,
        tmdb_id INTEGER,
        tvdb_id INTEGER,
        title TEXT NOT NULL,
        year INTEGER,
        poster_url TEXT,
        backdrop_url TEXT,
        total_seasons INTEGER DEFAULT 0,
        total_episodes INTEGER DEFAULT 0,
        mode TEXT DEFAULT 'auto', -- 'auto', 'generator_only', 'mediux_locked', 'ignored'
        mediux_set_url TEXT,
        status TEXT DEFAULT 'Returning Series',
        library_section_id TEXT,
        library_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Safe column migrations for shows table
    cursor.execute("PRAGMA table_info(shows)")
    show_columns = [col[1] for col in cursor.fetchall()]
    if "status" not in show_columns:
        cursor.execute("ALTER TABLE shows ADD COLUMN status TEXT DEFAULT 'Returning Series'")
    if "tvdb_id" not in show_columns:
        cursor.execute("ALTER TABLE shows ADD COLUMN tvdb_id INTEGER")
    if "library_section_id" not in show_columns:
        cursor.execute("ALTER TABLE shows ADD COLUMN library_section_id TEXT")
    if "library_name" not in show_columns:
        cursor.execute("ALTER TABLE shows ADD COLUMN library_name TEXT")

    # Backfill legacy shows where library_section_id is NULL
    cursor.execute("""
        UPDATE shows 
        SET library_section_id = COALESCE((SELECT value FROM settings WHERE key = 'active_plex_library'), '1'),
            library_name = ?
        WHERE library_section_id IS NULL
    """, (PLEX_TV_LIBRARY,))

    # Show styling configuration (for generator)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS show_styles (
        rating_key TEXT PRIMARY KEY,
        layout TEXT DEFAULT 'standard',
        text_position TEXT DEFAULT 'left_center', -- 'left_center', 'left_bottom', 'center_bottom', 'right_center', 'right_bottom'
        font_family TEXT DEFAULT 'Oswald',
        subheading_font_family TEXT DEFAULT NULL,
        font_color TEXT DEFAULT '#FFFFFF',
        subheading_color TEXT DEFAULT '#A3A3A3',
        gradient_side TEXT DEFAULT 'left',
        gradient_width_pct INTEGER DEFAULT 48,
        gradient_opacity_pct INTEGER DEFAULT 88,
        show_subheading INTEGER DEFAULT 1,
        subheading_format TEXT DEFAULT 'SEASON {season_word} {icon} EPISODE {episode_word}',
        subheading_icon TEXT DEFAULT 'dot', -- 'dot', 'delta', 'dash', 'none'
        ai_prompt TEXT,
        has_custom_style INTEGER DEFAULT 0,
        title_font_size INTEGER DEFAULT 108,
        subheading_font_size INTEGER DEFAULT 52,
        text_box_width_pct INTEGER DEFAULT 46,
        subheading_gap INTEGER DEFAULT 16,
        subheading_casing TEXT DEFAULT 'upper',
        subheading_position TEXT DEFAULT 'above',
        subheading_tracking INTEGER DEFAULT 0,
        frosted_blur_pct INTEGER DEFAULT 0,
        film_grain_pct INTEGER DEFAULT 0,
        vignette_pct INTEGER DEFAULT 0,
        text_shadow_mode TEXT DEFAULT 'subtle',
        show_logo INTEGER DEFAULT 0,
        logo_position TEXT DEFAULT 'top_right',
        logo_opacity_pct INTEGER DEFAULT 80,
        logo_monochrome INTEGER DEFAULT 1,
        FOREIGN KEY(rating_key) REFERENCES shows(rating_key) ON DELETE CASCADE
    )
    """)
    
    # Safe column migrations if columns don't exist in existing database
    cursor.execute("PRAGMA table_info(show_styles)")
    columns = [col[1] for col in cursor.fetchall()]
    if "text_position" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN text_position TEXT DEFAULT 'left_center'")
    if "has_custom_style" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN has_custom_style INTEGER DEFAULT 0")
    if "title_font_size" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN title_font_size INTEGER DEFAULT 108")
    if "subheading_font_size" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN subheading_font_size INTEGER DEFAULT 52")
    if "text_box_width_pct" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN text_box_width_pct INTEGER DEFAULT 46")
    if "subheading_gap" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN subheading_gap INTEGER DEFAULT 16")
    if "subheading_font_family" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN subheading_font_family TEXT DEFAULT NULL")
    if "subheading_casing" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN subheading_casing TEXT DEFAULT 'upper'")
    if "subheading_position" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN subheading_position TEXT DEFAULT 'above'")
    if "subheading_tracking" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN subheading_tracking INTEGER DEFAULT 0")
    if "frosted_blur_pct" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN frosted_blur_pct INTEGER DEFAULT 0")
    if "film_grain_pct" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN film_grain_pct INTEGER DEFAULT 0")
    if "vignette_pct" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN vignette_pct INTEGER DEFAULT 0")
    if "text_shadow_mode" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN text_shadow_mode TEXT DEFAULT 'subtle'")
    if "show_logo" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN show_logo INTEGER DEFAULT 0")
    if "logo_position" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN logo_position TEXT DEFAULT 'top_right'")
    if "logo_opacity_pct" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN logo_opacity_pct INTEGER DEFAULT 80")
    if "logo_monochrome" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN logo_monochrome INTEGER DEFAULT 1")
    
    # Episode records and card status
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS episodes (
        rating_key TEXT PRIMARY KEY,
        show_rating_key TEXT NOT NULL,
        season_number INTEGER NOT NULL,
        episode_number INTEGER NOT NULL,
        title TEXT NOT NULL,
        card_source TEXT DEFAULT 'none', -- 'mediux', 'generator_interim', 'generator_preset', 'plex_native'
        card_url TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(show_rating_key) REFERENCES shows(rating_key) ON DELETE CASCADE
    )
    """)
    # Season poster tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS season_posters (
        season_rating_key TEXT PRIMARY KEY,
        show_rating_key TEXT NOT NULL,
        season_number INTEGER NOT NULL,
        poster_url TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(show_rating_key) REFERENCES shows(rating_key) ON DELETE CASCADE
    )
    """)

    # Episode still overrides (when user picks a specific candidate still from TMDb)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS episode_still_overrides (
        rating_key TEXT NOT NULL,
        season_number INTEGER NOT NULL,
        episode_number INTEGER NOT NULL,
        still_path TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (rating_key, season_number, episode_number),
        FOREIGN KEY(rating_key) REFERENCES shows(rating_key) ON DELETE CASCADE
    )
    """)

    # App settings key-value store
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    from backend.config import DEFAULT_METADATA_PROVIDER
    default_settings = {
        "auto_gemini_suggestion": "true",
        "default_new_show_mode": "ignored",
        "preferred_mediux_creators": "",
        "auto_smart_pick_stills": "true",
        "metadata_provider_priority": DEFAULT_METADATA_PROVIDER or "tvdb"
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

SYSTEM_DEFAULT_STYLE = {
    "layout": "standard",
    "text_position": "left_center",
    "font_family": "Oswald",
    "subheading_font_family": None,
    "font_color": "#FFFFFF",
    "subheading_color": "#A3A3A3",
    "gradient_side": "left",
    "gradient_width_pct": 48,
    "gradient_opacity_pct": 88,
    "show_subheading": 1,
    "subheading_format": "s_pad_ep_num",
    "subheading_icon": "dot",
    "title_font_size": 108,
    "subheading_font_size": 52,
    "text_box_width_pct": 46,
    "subheading_gap": 16,
    "subheading_casing": "upper",
    "subheading_position": "above",
    "subheading_tracking": 0,
    "frosted_blur_pct": 0,
    "film_grain_pct": 0,
    "vignette_pct": 0,
    "text_shadow_mode": "subtle",
    "show_logo": 0,
    "logo_position": "top_right",
    "logo_opacity_pct": 80,
    "logo_monochrome": 1
}

def get_default_generator_style() -> Dict[str, Any]:
    raw = get_setting("default_generator_style", "")
    if raw:
        try:
            custom = json.loads(raw)
            return {**SYSTEM_DEFAULT_STYLE, **custom}
        except Exception:
            pass
    return dict(SYSTEM_DEFAULT_STYLE)

def set_default_generator_style(style_dict: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**SYSTEM_DEFAULT_STYLE, **style_dict}
    set_setting("default_generator_style", json.dumps(merged))
    return merged

def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

def bulk_update_show_modes(mode: str) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE shows SET mode = ?, updated_at = CURRENT_TIMESTAMP", (mode,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def upsert_show(show_data: Dict[str, Any]):
    default_mode = get_setting("default_new_show_mode", "ignored")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO shows (rating_key, tmdb_id, tvdb_id, title, year, poster_url, backdrop_url, total_seasons, total_episodes, mode, mediux_set_url, status, library_section_id, library_name, updated_at)
    VALUES (:rating_key, :tmdb_id, :tvdb_id, :title, :year, :poster_url, :backdrop_url, :total_seasons, :total_episodes, 
            COALESCE((SELECT mode FROM shows WHERE rating_key = :rating_key), :default_mode),
            COALESCE((SELECT mediux_set_url FROM shows WHERE rating_key = :rating_key), NULL),
            COALESCE(:status, (SELECT status FROM shows WHERE rating_key = :rating_key), 'Returning Series'),
            :library_section_id, :library_name,
            CURRENT_TIMESTAMP)
    ON CONFLICT(rating_key) DO UPDATE SET
        tmdb_id = COALESCE(excluded.tmdb_id, shows.tmdb_id),
        tvdb_id = COALESCE(excluded.tvdb_id, shows.tvdb_id),
        title = excluded.title,
        year = excluded.year,
        poster_url = COALESCE(excluded.poster_url, shows.poster_url),
        backdrop_url = COALESCE(excluded.backdrop_url, shows.backdrop_url),
        total_seasons = excluded.total_seasons,
        total_episodes = excluded.total_episodes,
        status = COALESCE(excluded.status, shows.status),
        library_section_id = COALESCE(excluded.library_section_id, shows.library_section_id),
        library_name = COALESCE(excluded.library_name, shows.library_name),
        updated_at = CURRENT_TIMESTAMP
    """, {
        "rating_key": str(show_data["rating_key"]),
        "tmdb_id": show_data.get("tmdb_id"),
        "tvdb_id": show_data.get("tvdb_id"),
        "title": show_data["title"],
        "year": show_data.get("year"),
        "poster_url": show_data.get("poster_url"),
        "backdrop_url": show_data.get("backdrop_url"),
        "total_seasons": show_data.get("total_seasons", 0),
        "total_episodes": show_data.get("total_episodes", 0),
        "default_mode": default_mode,
        "status": show_data.get("status"),
        "library_section_id": str(show_data.get("library_section_id")) if show_data.get("library_section_id") else None,
        "library_name": show_data.get("library_name")
    })
    
    # Ensure default style exists (use user-configured default generator style)
    def_style = get_default_generator_style()
    cursor.execute("""
    INSERT INTO show_styles (
        rating_key, layout, text_position, font_family, subheading_font_family,
        font_color, subheading_color, gradient_side, gradient_width_pct, gradient_opacity_pct,
        show_subheading, subheading_format, subheading_icon,
        title_font_size, subheading_font_size, text_box_width_pct, subheading_gap,
        subheading_casing, subheading_position, subheading_tracking,
        frosted_blur_pct, film_grain_pct, vignette_pct, text_shadow_mode,
        show_logo, logo_position, logo_opacity_pct, logo_monochrome, has_custom_style
    ) VALUES (
        :rating_key, :layout, :text_position, :font_family, :subheading_font_family,
        :font_color, :subheading_color, :gradient_side, :gradient_width_pct, :gradient_opacity_pct,
        :show_subheading, :subheading_format, :subheading_icon,
        :title_font_size, :subheading_font_size, :text_box_width_pct, :subheading_gap,
        :subheading_casing, :subheading_position, :subheading_tracking,
        :frosted_blur_pct, :film_grain_pct, :vignette_pct, :text_shadow_mode,
        :show_logo, :logo_position, :logo_opacity_pct, :logo_monochrome, 0
    )
    ON CONFLICT(rating_key) DO NOTHING
    """, {
        "rating_key": str(show_data["rating_key"]),
        "layout": def_style.get("layout", "standard"),
        "text_position": def_style.get("text_position", "left_center"),
        "font_family": def_style.get("font_family", "Oswald"),
        "subheading_font_family": def_style.get("subheading_font_family") or None,
        "font_color": def_style.get("font_color", "#FFFFFF"),
        "subheading_color": def_style.get("subheading_color", "#A3A3A3"),
        "gradient_side": def_style.get("gradient_side", "left"),
        "gradient_width_pct": def_style.get("gradient_width_pct", 48),
        "gradient_opacity_pct": def_style.get("gradient_opacity_pct", 88),
        "show_subheading": def_style.get("show_subheading", 1),
        "subheading_format": def_style.get("subheading_format", "s_pad_ep_num"),
        "subheading_icon": def_style.get("subheading_icon", "dot"),
        "title_font_size": def_style.get("title_font_size", 108),
        "subheading_font_size": def_style.get("subheading_font_size", 52),
        "text_box_width_pct": def_style.get("text_box_width_pct", 46),
        "subheading_gap": def_style.get("subheading_gap", 16),
        "subheading_casing": def_style.get("subheading_casing", "upper"),
        "subheading_position": def_style.get("subheading_position", "above"),
        "subheading_tracking": def_style.get("subheading_tracking", 0),
        "frosted_blur_pct": def_style.get("frosted_blur_pct", 0),
        "film_grain_pct": def_style.get("film_grain_pct", 0),
        "vignette_pct": def_style.get("vignette_pct", 0),
        "text_shadow_mode": def_style.get("text_shadow_mode", "subtle"),
        "show_logo": def_style.get("show_logo", 0),
        "logo_position": def_style.get("logo_position", "top_right"),
        "logo_opacity_pct": def_style.get("logo_opacity_pct", 80),
        "logo_monochrome": def_style.get("logo_monochrome", 1)
    })
    
    conn.commit()
    conn.close()

def update_show_status(rating_key: str, status: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE shows SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE rating_key = ?", (status, str(rating_key)))
    conn.commit()
    conn.close()

def get_show(rating_key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, st.layout, st.text_position, st.font_family, st.subheading_font_family, st.font_color, st.subheading_color, 
           st.gradient_side, st.gradient_width_pct, st.gradient_opacity_pct, 
           st.show_subheading, st.subheading_format, st.subheading_icon, st.ai_prompt,
           st.has_custom_style,
           COALESCE(st.title_font_size, 108) AS title_font_size,
           COALESCE(st.subheading_font_size, 52) AS subheading_font_size,
           COALESCE(st.text_box_width_pct, 46) AS text_box_width_pct,
           COALESCE(st.subheading_gap, 16) AS subheading_gap,
           COALESCE(st.subheading_casing, 'upper') AS subheading_casing,
           COALESCE(st.subheading_position, 'above') AS subheading_position,
           COALESCE(st.subheading_tracking, 0) AS subheading_tracking,
           COALESCE(st.frosted_blur_pct, 0) AS frosted_blur_pct,
           COALESCE(st.film_grain_pct, 0) AS film_grain_pct,
           COALESCE(st.vignette_pct, 0) AS vignette_pct,
           COALESCE(st.text_shadow_mode, 'subtle') AS text_shadow_mode,
           COALESCE(st.show_logo, 0) AS show_logo,
           COALESCE(st.logo_position, 'top_right') AS logo_position,
           COALESCE(st.logo_opacity_pct, 80) AS logo_opacity_pct,
           COALESCE(st.logo_monochrome, 1) AS logo_monochrome
    FROM shows s
    LEFT JOIN show_styles st ON s.rating_key = st.rating_key
    WHERE s.rating_key = ?
    """, (rating_key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_shows(library_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    query = """
    SELECT s.*, 
           st.layout, st.text_position, st.font_family, st.subheading_font_family, st.font_color, st.subheading_color, 
           st.gradient_side, st.gradient_width_pct, st.gradient_opacity_pct, 
           st.show_subheading, st.subheading_format, st.subheading_icon, st.ai_prompt,
           COALESCE(st.has_custom_style, 0) AS has_custom_style,
           COALESCE(st.title_font_size, 108) AS title_font_size,
           COALESCE(st.subheading_font_size, 52) AS subheading_font_size,
           COALESCE(st.text_box_width_pct, 46) AS text_box_width_pct,
           COALESCE(st.subheading_gap, 16) AS subheading_gap,
           COALESCE(st.subheading_casing, 'upper') AS subheading_casing,
           COALESCE(st.subheading_position, 'above') AS subheading_position,
           COALESCE(st.subheading_tracking, 0) AS subheading_tracking,
           COALESCE(st.frosted_blur_pct, 0) AS frosted_blur_pct,
           COALESCE(st.film_grain_pct, 0) AS film_grain_pct,
           COALESCE(st.vignette_pct, 0) AS vignette_pct,
           COALESCE(st.text_shadow_mode, 'subtle') AS text_shadow_mode,
           COALESCE(st.show_logo, 0) AS show_logo,
           COALESCE(st.logo_position, 'top_right') AS logo_position,
           COALESCE(st.logo_opacity_pct, 80) AS logo_opacity_pct,
           COALESCE(st.logo_monochrome, 1) AS logo_monochrome,
           (SELECT COUNT(*) FROM episodes e WHERE e.show_rating_key = s.rating_key AND e.card_source = 'mediux') AS mediux_cards_count,
           (SELECT COUNT(*) FROM episodes e WHERE e.show_rating_key = s.rating_key AND e.card_source LIKE 'generator%') AS generator_cards_count
    FROM shows s
    LEFT JOIN show_styles st ON s.rating_key = st.rating_key
    """
    params = []
    if library_filter and library_filter.lower() != "all":
        query += " WHERE (s.library_section_id = ? OR s.library_name = ?)"
        params.extend([str(library_filter), str(library_filter)])
    query += " ORDER BY s.title ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_indexed_libraries() -> List[Dict[str, Any]]:
    """Return all distinct libraries present in the local database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT library_section_id, library_name, COUNT(*) as show_count
        FROM shows
        WHERE library_name IS NOT NULL
        GROUP BY library_section_id, library_name
        ORDER BY library_name ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def update_show_mode(rating_key: str, mode: str, mediux_set_url: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE shows 
    SET mode = ?, mediux_set_url = ?, updated_at = CURRENT_TIMESTAMP
    WHERE rating_key = ?
    """, (mode, mediux_set_url, rating_key))
    conn.commit()
    conn.close()

def update_show_style(rating_key: str, style_data: Dict[str, Any]):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO show_styles (rating_key, layout, text_position, font_family, subheading_font_family, font_color, subheading_color, 
                             gradient_side, gradient_width_pct, gradient_opacity_pct, 
                             show_subheading, subheading_format, subheading_icon, ai_prompt, has_custom_style,
                             title_font_size, subheading_font_size, text_box_width_pct, subheading_gap,
                             subheading_casing, subheading_position, subheading_tracking,
                             frosted_blur_pct, film_grain_pct, vignette_pct, text_shadow_mode,
                             show_logo, logo_position, logo_opacity_pct, logo_monochrome)
    VALUES (:rating_key, 
            COALESCE(:layout, 'standard'), 
            COALESCE(:text_position, 'left_center'), 
            COALESCE(:font_family, 'Oswald'), 
            :subheading_font_family,
            COALESCE(:font_color, '#FFFFFF'), 
            COALESCE(:subheading_color, '#A3A3A3'), 
            COALESCE(:gradient_side, 'left'), 
            COALESCE(:gradient_width_pct, 48), 
            COALESCE(:gradient_opacity_pct, 88), 
            COALESCE(:show_subheading, 1), 
            COALESCE(:subheading_format, 'SEASON {season_word} {icon} EPISODE {episode_word}'), 
            COALESCE(:subheading_icon, 'dot'), 
            :ai_prompt, 
            COALESCE(:has_custom_style, 1),
            COALESCE(:title_font_size, 108),
            COALESCE(:subheading_font_size, 52),
            COALESCE(:text_box_width_pct, 46),
            COALESCE(:subheading_gap, 16),
            COALESCE(:subheading_casing, 'upper'),
            COALESCE(:subheading_position, 'above'),
            COALESCE(:subheading_tracking, 0),
            COALESCE(:frosted_blur_pct, 0),
            COALESCE(:film_grain_pct, 0),
            COALESCE(:vignette_pct, 0),
            COALESCE(:text_shadow_mode, 'subtle'),
            COALESCE(:show_logo, 0),
            COALESCE(:logo_position, 'top_right'),
            COALESCE(:logo_opacity_pct, 80),
            COALESCE(:logo_monochrome, 1))
    ON CONFLICT(rating_key) DO UPDATE SET
        layout = COALESCE(excluded.layout, show_styles.layout),
        text_position = COALESCE(excluded.text_position, show_styles.text_position),
        font_family = COALESCE(excluded.font_family, show_styles.font_family),
        subheading_font_family = excluded.subheading_font_family,
        font_color = COALESCE(excluded.font_color, show_styles.font_color),
        subheading_color = COALESCE(excluded.subheading_color, show_styles.subheading_color),
        gradient_side = COALESCE(excluded.gradient_side, show_styles.gradient_side),
        gradient_width_pct = COALESCE(excluded.gradient_width_pct, show_styles.gradient_width_pct),
        gradient_opacity_pct = COALESCE(excluded.gradient_opacity_pct, show_styles.gradient_opacity_pct),
        show_subheading = COALESCE(excluded.show_subheading, show_styles.show_subheading),
        subheading_format = COALESCE(excluded.subheading_format, show_styles.subheading_format),
        subheading_icon = COALESCE(excluded.subheading_icon, show_styles.subheading_icon),
        ai_prompt = COALESCE(excluded.ai_prompt, show_styles.ai_prompt),
        has_custom_style = COALESCE(excluded.has_custom_style, 1),
        title_font_size = COALESCE(excluded.title_font_size, show_styles.title_font_size),
        subheading_font_size = COALESCE(excluded.subheading_font_size, show_styles.subheading_font_size),
        text_box_width_pct = COALESCE(excluded.text_box_width_pct, show_styles.text_box_width_pct),
        subheading_gap = COALESCE(excluded.subheading_gap, show_styles.subheading_gap),
        subheading_casing = COALESCE(excluded.subheading_casing, show_styles.subheading_casing),
        subheading_position = COALESCE(excluded.subheading_position, show_styles.subheading_position),
        subheading_tracking = COALESCE(excluded.subheading_tracking, show_styles.subheading_tracking),
        frosted_blur_pct = COALESCE(excluded.frosted_blur_pct, show_styles.frosted_blur_pct),
        film_grain_pct = COALESCE(excluded.film_grain_pct, show_styles.film_grain_pct),
        vignette_pct = COALESCE(excluded.vignette_pct, show_styles.vignette_pct),
        text_shadow_mode = COALESCE(excluded.text_shadow_mode, show_styles.text_shadow_mode),
        show_logo = COALESCE(excluded.show_logo, show_styles.show_logo),
        logo_position = COALESCE(excluded.logo_position, show_styles.logo_position),
        logo_opacity_pct = COALESCE(excluded.logo_opacity_pct, show_styles.logo_opacity_pct),
        logo_monochrome = COALESCE(excluded.logo_monochrome, show_styles.logo_monochrome)
    """, {
        "layout": style_data.get("layout"),
        "text_position": style_data.get("text_position"),
        "font_family": style_data.get("font_family"),
        "subheading_font_family": style_data.get("subheading_font_family"),
        "font_color": style_data.get("font_color"),
        "subheading_color": style_data.get("subheading_color"),
        "gradient_side": style_data.get("gradient_side"),
        "gradient_width_pct": style_data.get("gradient_width_pct"),
        "gradient_opacity_pct": style_data.get("gradient_opacity_pct"),
        "show_subheading": style_data.get("show_subheading"),
        "subheading_format": style_data.get("subheading_format"),
        "subheading_icon": style_data.get("subheading_icon"),
        "ai_prompt": style_data.get("ai_prompt"),
        "has_custom_style": style_data.get("has_custom_style", 1),
        "title_font_size": style_data.get("title_font_size"),
        "subheading_font_size": style_data.get("subheading_font_size"),
        "text_box_width_pct": style_data.get("text_box_width_pct"),
        "subheading_gap": style_data.get("subheading_gap"),
        "subheading_casing": style_data.get("subheading_casing"),
        "subheading_position": style_data.get("subheading_position"),
        "subheading_tracking": style_data.get("subheading_tracking"),
        "frosted_blur_pct": style_data.get("frosted_blur_pct"),
        "film_grain_pct": style_data.get("film_grain_pct"),
        "vignette_pct": style_data.get("vignette_pct"),
        "text_shadow_mode": style_data.get("text_shadow_mode"),
        "show_logo": style_data.get("show_logo"),
        "logo_position": style_data.get("logo_position"),
        "logo_opacity_pct": style_data.get("logo_opacity_pct"),
        "logo_monochrome": style_data.get("logo_monochrome"),
        "rating_key": rating_key
    })
    conn.commit()
    conn.close()

def update_show_tmdb_id(
    rating_key: str, 
    tmdb_id: Optional[int], 
    poster_url: Optional[str] = None, 
    backdrop_url: Optional[str] = None,
    status: Optional[str] = None
):
    """Update TMDb ID and optionally poster/backdrop URLs and status for a show."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE shows 
    SET tmdb_id = ?, 
        poster_url = COALESCE(?, poster_url), 
        backdrop_url = COALESCE(?, backdrop_url), 
        status = COALESCE(?, status),
        updated_at = CURRENT_TIMESTAMP
    WHERE rating_key = ?
    """, (tmdb_id, poster_url, backdrop_url, status, rating_key))
    conn.commit()
    conn.close()

def update_show_tvdb_id(
    rating_key: str, 
    tvdb_id: Optional[int], 
    poster_url: Optional[str] = None, 
    backdrop_url: Optional[str] = None,
    status: Optional[str] = None
):
    """Update TheTVDB ID and optionally poster/backdrop URLs and status for a show."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE shows 
    SET tvdb_id = ?, 
        poster_url = COALESCE(?, poster_url), 
        backdrop_url = COALESCE(?, backdrop_url), 
        status = COALESCE(?, status),
        updated_at = CURRENT_TIMESTAMP
    WHERE rating_key = ?
    """, (tvdb_id, poster_url, backdrop_url, status, rating_key))
    conn.commit()
    conn.close()

def get_show_season_posters(show_rating_key: str) -> Dict[int, str]:
    """Retrieve all uploaded season posters for a show."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT season_number, poster_url FROM season_posters WHERE show_rating_key = ?", (show_rating_key,))
    rows = cursor.fetchall()
    conn.close()
    return {r["season_number"]: r["poster_url"] for r in rows}

def record_season_poster(season_rating_key: str, show_rating_key: str, season_number: int, poster_url: str):
    """Record or update an uploaded season poster in SQLite."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO season_posters (season_rating_key, show_rating_key, season_number, poster_url, updated_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(season_rating_key) DO UPDATE SET
        poster_url = excluded.poster_url,
        updated_at = CURRENT_TIMESTAMP
    """, (str(season_rating_key), str(show_rating_key), season_number, poster_url))
    conn.commit()
    conn.close()

def get_episode_still_override(rating_key: str, season_number: int, episode_number: int) -> Optional[str]:
    """Retrieve custom TMDb still path override for a specific episode, if any."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT still_path FROM episode_still_overrides 
        WHERE rating_key = ? AND season_number = ? AND episode_number = ?
    """, (str(rating_key), int(season_number), int(episode_number)))
    row = cursor.fetchone()
    conn.close()
    return row["still_path"] if row else None

def set_episode_still_override(rating_key: str, season_number: int, episode_number: int, still_path: str):
    """Save or update custom TMDb still path override for an episode."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO episode_still_overrides (rating_key, season_number, episode_number, still_path, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(rating_key, season_number, episode_number) DO UPDATE SET
            still_path = excluded.still_path,
            updated_at = CURRENT_TIMESTAMP
    """, (str(rating_key), int(season_number), int(episode_number), str(still_path)))
    conn.commit()
    conn.close()

def delete_episode_still_override(rating_key: str, season_number: int, episode_number: int):
    """Remove custom still override and revert back to TMDb default."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM episode_still_overrides 
        WHERE rating_key = ? AND season_number = ? AND episode_number = ?
    """, (str(rating_key), int(season_number), int(episode_number)))
    conn.commit()
    conn.close()

def get_all_still_overrides_for_show(rating_key: str) -> Dict[str, str]:
    """Retrieve all still overrides for a show formatted as {'s_e': still_path}."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT season_number, episode_number, still_path 
        FROM episode_still_overrides 
        WHERE rating_key = ?
    """, (str(rating_key),))
    rows = cursor.fetchall()
    conn.close()
    return {f"{r['season_number']}_{r['episode_number']}": r["still_path"] for r in rows}

def get_episodes_for_show(rating_key: str) -> List[Dict[str, Any]]:
    """Retrieve all indexed episodes for a show from local database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rating_key, show_rating_key, season_number, episode_number, title, card_source, card_url 
        FROM episodes 
        WHERE show_rating_key = ? 
        ORDER BY season_number ASC, episode_number ASC
    """, (str(rating_key),))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows




