import sqlite3
from typing import Dict, List, Optional, Any
from backend.config import DB_PATH

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
        title TEXT NOT NULL,
        year INTEGER,
        poster_url TEXT,
        backdrop_url TEXT,
        total_seasons INTEGER DEFAULT 0,
        total_episodes INTEGER DEFAULT 0,
        mode TEXT DEFAULT 'ignored', -- 'auto', 'generator_only', 'mediux_locked', 'ignored'
        mediux_set_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Show styling configuration (for generator)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS show_styles (
        rating_key TEXT PRIMARY KEY,
        layout TEXT DEFAULT 'standard',
        text_position TEXT DEFAULT 'left_center', -- 'left_center', 'left_bottom', 'center_bottom', 'right_center', 'right_bottom'
        font_family TEXT DEFAULT 'Montserrat',
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
        title_font_size INTEGER DEFAULT 82,
        subheading_font_size INTEGER DEFAULT 34,
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
        cursor.execute("ALTER TABLE show_styles ADD COLUMN title_font_size INTEGER DEFAULT 82")
    if "subheading_font_size" not in columns:
        cursor.execute("ALTER TABLE show_styles ADD COLUMN subheading_font_size INTEGER DEFAULT 34")
    
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

    # App settings key-value store
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    default_settings = {
        "auto_gemini_suggestion": "true",
        "default_new_show_mode": "ignored",
        "preferred_mediux_creators": ""
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

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
    INSERT INTO shows (rating_key, tmdb_id, title, year, poster_url, backdrop_url, total_seasons, total_episodes, mode, mediux_set_url, updated_at)
    VALUES (:rating_key, :tmdb_id, :title, :year, :poster_url, :backdrop_url, :total_seasons, :total_episodes, 
            COALESCE((SELECT mode FROM shows WHERE rating_key = :rating_key), :default_mode),
            COALESCE((SELECT mediux_set_url FROM shows WHERE rating_key = :rating_key), NULL),
            CURRENT_TIMESTAMP)
    ON CONFLICT(rating_key) DO UPDATE SET
        tmdb_id = excluded.tmdb_id,
        title = excluded.title,
        year = excluded.year,
        poster_url = excluded.poster_url,
        backdrop_url = excluded.backdrop_url,
        total_seasons = excluded.total_seasons,
        total_episodes = excluded.total_episodes,
        updated_at = CURRENT_TIMESTAMP
    """, {**show_data, "default_mode": default_mode})
    
    # Ensure default style exists
    cursor.execute("""
    INSERT OR IGNORE INTO show_styles (rating_key) VALUES (:rating_key)
    """, {"rating_key": show_data["rating_key"]})
    
    conn.commit()
    conn.close()

def get_show(rating_key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, st.layout, st.text_position, st.font_family, st.font_color, st.subheading_color, 
           st.gradient_side, st.gradient_width_pct, st.gradient_opacity_pct, 
           st.show_subheading, st.subheading_format, st.subheading_icon, st.ai_prompt,
           st.has_custom_style,
           COALESCE(st.title_font_size, 82) AS title_font_size,
           COALESCE(st.subheading_font_size, 34) AS subheading_font_size
    FROM shows s
    LEFT JOIN show_styles st ON s.rating_key = st.rating_key
    WHERE s.rating_key = ?
    """, (rating_key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_shows() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, 
           st.layout, st.text_position, st.font_family, st.font_color, st.subheading_color, 
           st.gradient_side, st.gradient_width_pct, st.gradient_opacity_pct, 
           st.show_subheading, st.subheading_format, st.subheading_icon, st.ai_prompt,
           COALESCE(st.has_custom_style, 0) AS has_custom_style,
           COALESCE(st.title_font_size, 82) AS title_font_size,
           COALESCE(st.subheading_font_size, 34) AS subheading_font_size,
           (SELECT COUNT(*) FROM episodes e WHERE e.show_rating_key = s.rating_key AND e.card_source = 'mediux') AS mediux_cards_count,
           (SELECT COUNT(*) FROM episodes e WHERE e.show_rating_key = s.rating_key AND e.card_source LIKE 'generator%') AS generator_cards_count
    FROM shows s
    LEFT JOIN show_styles st ON s.rating_key = st.rating_key
    ORDER BY s.title ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

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
    INSERT INTO show_styles (rating_key, layout, text_position, font_family, font_color, subheading_color, 
                             gradient_side, gradient_width_pct, gradient_opacity_pct, 
                             show_subheading, subheading_format, subheading_icon, ai_prompt, has_custom_style,
                             title_font_size, subheading_font_size)
    VALUES (:rating_key, 
            COALESCE(:layout, 'standard'), 
            COALESCE(:text_position, 'left_center'), 
            COALESCE(:font_family, 'Montserrat'), 
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
            COALESCE(:title_font_size, 82),
            COALESCE(:subheading_font_size, 34))
    ON CONFLICT(rating_key) DO UPDATE SET
        layout = COALESCE(excluded.layout, show_styles.layout),
        text_position = COALESCE(excluded.text_position, show_styles.text_position),
        font_family = COALESCE(excluded.font_family, show_styles.font_family),
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
        subheading_font_size = COALESCE(excluded.subheading_font_size, show_styles.subheading_font_size)
    """, {
        "layout": style_data.get("layout"),
        "text_position": style_data.get("text_position"),
        "font_family": style_data.get("font_family"),
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
        "rating_key": rating_key
    })
    conn.commit()
    conn.close()

def update_show_tmdb_id(
    rating_key: str, 
    tmdb_id: Optional[int], 
    poster_url: Optional[str] = None, 
    backdrop_url: Optional[str] = None
):
    """Update TMDb ID and optionally poster/backdrop URLs for a show."""
    conn = get_db()
    cursor = conn.cursor()
    if poster_url and backdrop_url:
        cursor.execute("""
        UPDATE shows 
        SET tmdb_id = ?, poster_url = COALESCE(?, poster_url), backdrop_url = COALESCE(?, backdrop_url), updated_at = CURRENT_TIMESTAMP
        WHERE rating_key = ?
        """, (tmdb_id, poster_url, backdrop_url, rating_key))
    elif poster_url:
        cursor.execute("""
        UPDATE shows 
        SET tmdb_id = ?, poster_url = COALESCE(?, poster_url), updated_at = CURRENT_TIMESTAMP
        WHERE rating_key = ?
        """, (tmdb_id, poster_url, rating_key))
    elif backdrop_url:
        cursor.execute("""
        UPDATE shows 
        SET tmdb_id = ?, backdrop_url = COALESCE(?, backdrop_url), updated_at = CURRENT_TIMESTAMP
        WHERE rating_key = ?
        """, (tmdb_id, backdrop_url, rating_key))
    else:
        cursor.execute("""
        UPDATE shows 
        SET tmdb_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE rating_key = ?
        """, (tmdb_id, rating_key))
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


