import json
import logging
from typing import Dict, Any, Optional
from backend.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

class AIStyler:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini client: {e}")

    def suggest_style(
        self,
        show_title: str,
        genres: list,
        overview: str,
        user_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ask Gemini for optimal typography, colors, and layout for a show."""
        if not self._client:
            return {
                "font_family": "Oswald",
                "font_color": "#FFFFFF",
                "subheading_color": "#D1D5DB",
                "gradient_side": "left",
                "gradient_width_pct": 48,
                "gradient_opacity_pct": 90,
                "subheading_icon": "•",
                "reasoning": "Default styling applied (Gemini key not configured)."
            }

        prompt = f"""
You are an elite graphic design and television branding expert specializing in title cards and cinematic typography for Plex.
Analyze the following TV show and recommend optimal title card typography, color palette, and layout parameters:

Show: {show_title}
Genres: {', '.join(genres) if genres else 'Unknown'}
Overview: {overview[:300] if overview else 'N/A'}
User Style Direction: {user_prompt or 'Match the authentic tone, genre, and aesthetic of the series.'}

--- CRITICAL DESIGN & READABILITY RULES ---
1. READABILITY IS PARAMOUNT:
   - Title cards are viewed from across the room on television screens, home theater projectors, and mobile displays.
   - Text must be immediately legible and readable at a glance over photographic, potentially bright or busy episode background images.
   - Choose fonts with strong glyph definition and clean letterforms. Never choose illegible decorative or spindly script fonts for episode titles.

2. TYPOGRAPHY DIVERSITY BY GENRE:
   Select a distinctive, high-quality open-source font tailored to the show's aesthetic from Google Fonts / open font libraries:
   - Sci-Fi / Cyberpunk / Tech: Orbitron, Michroma, Space Grotesk, Syne, Rajdhani, Audiowide, Exo 2
   - Thriller / Crime / Action: Bebas Neue, Oswald, Anton, Barlow Condensed, Teko, Archivo Black
   - Prestige Drama / Mystery / Romance: Cinzel, Playfair Display, Bodoni Moda, Cormorant Garamond, Prata, DM Serif Display
   - Comedy / Animation / Light Drama: Montserrat, Poppins, Jost, Outfit, Rubik, Lexend
   - Horror / Dark Fantasy / Supernatural: Cinzel Decorative, Syne, Creepster, Rye, UnifrakturMaguntia
   - Documentary / Neo-Noir / Procedural: Inter, Work Sans, DM Sans, Oswald, Chivo
   If the show has iconic branding, provide the closest open-source equivalent.

3. GRADIENT USAGE & PLACEMENT:
   - The rendering engine applies a smooth, dark shadow gradient (black fading to transparent) directly behind the text area to guarantee contrast against bright or dynamic episode imagery.
   - You MUST align "gradient_side" with "text_position":
     * If "text_position" contains "bottom" ("center_bottom", "left_bottom", "right_bottom"), use "gradient_side": "bottom".
     * If "text_position" is "left_center", use "gradient_side": "left".
     * If "text_position" is "right_center", use "gradient_side": "right".
   - "gradient_width_pct": Integer between 40 and 55 (covers the text footprint cleanly without overwhelming the backdrop).
   - "gradient_opacity_pct": Integer between 82 and 95 (dense enough so white/bright scenes in the backdrop artwork do not bleed through and reduce legibility).

4. TEXT COLORS & HIGH-CONTRAST PALETTE:
   - Because the gradient behind the text is a DARK SHADOW (black/charcoal fade), all text colors MUST have HIGH LUMINANCE AND CONTRAST against a dark background.
   - NEVER choose dark or low-contrast colors (e.g. navy, dark red, dark purple, forest green, dark gray/charcoal, muddy brown) as they will vanish into the gradient shadow and become unreadable.
   - "font_color": Must be a high-luminance, eye-catching color that captures the show's spirit. Great choices include crisp white ("#FFFFFF"), bright warm ivory ("#FFF8E7"), golden amber ("#F4B84D", "#E5A00D"), cyber/electric cyan ("#00E5FF"), neon/acid accents ("#39FF14", "#FF5252"), or vibrant sunshine yellow ("#FFD600").
   - "subheading_color": Must complement "font_color" while remaining crisp and easily readable against the dark gradient shadow. Use bright neutral tones (e.g. "#D1D5DB", "#E5E7EB", "#A3A3A3") or a lighter tonal companion to the title color. Never use dark grays (below #9CA3AF).

Return ONLY a JSON object with these exact keys:
- "font_family": Name of the selected open-source font (Google Fonts compatible). The server will automatically fetch it on the fly.
- "title_font_size": Integer between 65 and 105 (default 82). Bold, condensed display fonts (like Bebas Neue, Anton, Oswald) shine at larger sizes (e.g. 90-100). Ornate or wider serifs (like Cinzel, Bodoni Moda) are best at 72-82.
- "subheading_font_size": Integer between 26 and 40 (default 34). Proportional companion size to the title font.
- "font_color": High-luminance hex color code for the main episode title (e.g. "#FFFFFF", "#F4B84D", "#00E5FF", "#FF5252", "#E0E0E0")
- "subheading_color": Complementary, readable hex color for season/episode text (e.g. "#E5E7EB", "#D1D5DB", "#F4B84D")
- "text_position": One of ["left_center", "left_bottom", "center_bottom", "right_center", "right_bottom"]
- "gradient_side": "left", "bottom", or "right" (must strictly match text_position as described above)
- "gradient_width_pct": Integer between 40 and 55
- "gradient_opacity_pct": Integer between 82 and 95
- "subheading_icon": A single character separator between season and episode text (e.g. "•", "-", ":", "|", ".", "/", "~", "=" or "" for none). NEVER suggest deltas or logos; always use a clean typographical character separator that complements the show's typography.
- "reasoning": 1-2 sentences explaining how the font choice, size, and palette capture the show's aesthetic while maximizing legibility against the gradient.
"""

        try:
            from google.genai import types
            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    response_mime_type="application/json"
                )
            )
            raw_text = response.text.strip()
            data = json.loads(raw_text)

            # Defensive post-processing: enforce gradient placement matches text position
            text_pos = data.get("text_position", "left_center")
            if "bottom" in text_pos and data.get("gradient_side") != "bottom":
                data["gradient_side"] = "bottom"
            elif "right" in text_pos and data.get("gradient_side") not in ("right", "bottom"):
                data["gradient_side"] = "right"
            elif "left" in text_pos and data.get("gradient_side") not in ("left", "bottom"):
                data["gradient_side"] = "left"

            # Defensive post-processing: font sizes bounds
            try:
                tfs = int(data.get("title_font_size", 82))
                data["title_font_size"] = max(40, min(140, tfs))
            except Exception:
                data["title_font_size"] = 82

            try:
                sfs = int(data.get("subheading_font_size", 34))
                data["subheading_font_size"] = max(20, min(60, sfs))
            except Exception:
                data["subheading_font_size"] = 34

            # Defensive post-processing: verify text colors have sufficient luminance against dark gradient
            def _is_too_dark(hex_str: str) -> bool:
                try:
                    h = hex_str.strip().lstrip("#")
                    if len(h) == 6:
                        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                        return lum < 0.25
                except Exception:
                    pass
                return False

            if _is_too_dark(data.get("font_color", "")):
                data["font_color"] = "#FFFFFF"
            if _is_too_dark(data.get("subheading_color", "")):
                data["subheading_color"] = "#D1D5DB"

            return data
        except Exception as e:
            err_str = str(e)
            logger.error(f"Gemini style suggestion failed: {err_str}")

            is_503 = any(token in err_str for token in ["503", "UNAVAILABLE", "high demand", "Service Unavailable"])
            is_quota = any(token in err_str for token in ["429", "RESOURCE_EXHAUSTED", "quota", "limit reached"])

            if is_503:
                user_msg = f"Gemini ({GEMINI_MODEL}) is currently experiencing high demand (503 Service Unavailable). Please try again in a few moments."
            elif is_quota:
                user_msg = f"Gemini API rate limit reached (429 Quota Exceeded for {GEMINI_MODEL}). Please wait a moment before trying again."
            else:
                user_msg = f"Gemini style suggestion failed: {err_str[:150]}"

            return {
                "error": user_msg,
                "is_unavailable": is_503,
                "font_family": "Oswald",
                "font_color": "#FFFFFF",
                "subheading_color": "#D1D5DB",
                "gradient_side": "left",
                "gradient_width_pct": 48,
                "gradient_opacity_pct": 90,
                "subheading_icon": "•",
                "reasoning": user_msg
            }

