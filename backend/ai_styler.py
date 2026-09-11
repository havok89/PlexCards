import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from PIL import Image
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
        user_prompt: Optional[str] = None,
        poster_path: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Ask Gemini for optimal typography, font pairing, colors, layout, and subheading styling for a show."""
        if not self._client:
            return {
                "font_family": "Oswald",
                "subheading_font_family": "Oswald",
                "font_color": "#FFFFFF",
                "subheading_color": "#D1D5DB",
                "gradient_side": "left",
                "gradient_width_pct": 48,
                "gradient_opacity_pct": 90,
                "subheading_icon": "•",
                "title_font_size": 108,
                "subheading_font_size": 44,
                "text_position": "left_center",
                "subheading_position": "above",
                "subheading_casing": "upper",
                "subheading_tracking": 0,
                "subheading_format": "s_pad_ep_num",
                "subheading_gap": 14,
                "text_box_width_pct": 46,
                "reasoning": "Default styling applied (Gemini key not configured)."
            }

        # Try to load poster image for multimodal inspection
        poster_img = None
        if poster_path:
            try:
                p = Path(poster_path)
                if p.exists():
                    poster_img = Image.open(p)
            except Exception as img_err:
                logger.warning(f"Could not load poster image for AI styler: {img_err}")

        has_poster = poster_img is not None
        poster_instructions = """
An official promotional poster for this show is ATTACHED. Visually inspect the poster image closely:
1. POSTER LOGO & TYPOGRAPHY MATCHING:
   - Identify the typography style of the show title on the poster (e.g. stencil serif, bold condensed grotesque, techno geometric, retro 80s brush, hand-drawn comic, modern slab).
   - "font_family": Select the closest open-source Google Font equivalent for the main episode title that captures the exact spirit and letterforms of the poster logo.
   - "subheading_font_family": Select a complementary open-source Google Font for the subtitle (Season/Episode header). In professional title card design, font pairing is critical:
     * If "font_family" is an expressive or ornate display font (e.g. Cinzel, Bangers, Righteous, Teko, Playfair Display), pair it with a clean, solid grotesque or condensed sans-serif (such as Inter, Barlow Condensed, Rubik, Oswald, Outfit, Space Grotesk).
     * If "font_family" is already a clean modern sans-serif (e.g. Inter, Oswald), you may use the same font or a subtle companion.

2. COMPOSITION-AWARE TEXT POSITIONING:
   - Analyze the visual balance and focal points of the poster art (where main characters, faces, silhouettes, or horizon lines sit).
   - Choose a "text_position" (e.g. "left_center", "center_bottom", "left_bottom", "right_bottom", "top_left") that harmoniously frames the composition without covering critical focal elements.
   - You MUST strictly align "gradient_side" with "text_position":
     * If "text_position" contains "top", use "gradient_side": "top".
     * If "text_position" contains "bottom", use "gradient_side": "bottom".
     * If "text_position" is "left_center", use "gradient_side": "left".
     * If "text_position" is "right_center", use "gradient_side": "right".

3. PROPORTIONAL FONT SIZING & TEXT WRAP:
   - "title_font_size": Integer between 90 and 130 (default 108). Title cards are displayed scaled down (e.g. 5 in a row across TV screens). Bold condensed fonts shine at 110-125; ornate serifs are best around 96-112.
   - "subheading_font_size": Integer between 42 and 62 (default 52). Proportional companion size to title_font_size for effortless readability on TV displays.
   - "text_box_width_pct": Integer between 40 and 55 (default 46). Maximum width for multi-line titles before wrapping.

4. BRANDING COLOR PALETTE:
   - Sample eye-catching, high-contrast branding colors directly from the poster artwork (e.g. iconic neon accents, costume hues, glowing magic, warm gold, or toxic green).
   - "font_color": High-luminance hex color code (must contrast vividly against the dark shadow gradient).
   - "subheading_color": Complementary, readable hex color code for the subtitle.

5. SUBHEADING POSITIONING & TYPOGRAPHIC DETAILING:
   - "subheading_position": Choose "above" (classic title card with subtitle over title) or "below" (modern streaming card layout, e.g. Netflix/HBO style where the episode title is heroic on top and code is neatly anchored below).
   - "subheading_casing": One of ["upper", "title", "lower"]. "upper" is commanding and cinematic; "title" (e.g. "S01 - Episode 1") is sleek, modern, and editorial; "lower" is minimalist.
   - "subheading_tracking": Integer between 0 and 6 (letter-spacing in px). Wide tracking (3-6px) looks ultra-premium and cinematic for sans-serif subtitles; 0-2px for tight serifs.
   - "subheading_format": One of ["s_pad_ep_num", "season_num_ep_num", "s_pad_e_pad", "season_word_ep_word", "compact_pad"].
   - "subheading_icon": Separator character between season and episode text (e.g. "•", "-", ":", "/", or "" for none).
   - "subheading_gap": Integer between 12 and 30 (default 16, distance in px between title and subtitle).
""" if has_poster else """
Analyze the show's genres and synopsis to select optimal typography, font pairing, colors, and layout:
1. "font_family": High-quality open-source Google Font tailored to the show's aesthetic.
2. "subheading_font_family": Clean, complementary Google Font (e.g. Inter, Barlow Condensed, Rubik, or matching).
3. "title_font_size": Integer between 90 and 130 (default 108).
4. "subheading_font_size": Integer between 42 and 62 (default 52).
5. "text_position": One of ["left_center", "left_bottom", "center_bottom", "right_center", "right_bottom", "top_left", "center"].
6. "gradient_side": Must match text_position ("left", "bottom", "right", "top").
7. "font_color" & "subheading_color": High-luminance hex colors.
8. "subheading_position": "above" or "below".
9. "subheading_casing": "upper", "title", or "lower".
10. "subheading_tracking": Integer between 0 and 6.
11. "subheading_format": "s_pad_ep_num", "season_num_ep_num", "s_pad_e_pad", "season_word_ep_word", or "compact_pad".
12. "subheading_icon": "•", "-", ":", "/", or "".
13. "subheading_gap": Integer between 12 and 30 (default 16).
14. "text_box_width_pct": Integer between 40 and 55 (default 46).
"""

        prompt = f"""
You are an elite graphic design and television branding expert specializing in title cards and cinematic typography for Plex.
Analyze the following TV show and recommend optimal title card typography, font pairing, color palette, layout parameters, and subheading styling:

Show: {show_title}
Genres: {', '.join(genres) if genres else 'Unknown'}
Overview: {overview[:300] if overview else 'N/A'}
User Style Direction: {user_prompt or 'Match the authentic tone, genre, and aesthetic of the series.'}

--- DESIGN INSTRUCTIONS ---
{poster_instructions}

--- CRITICAL DESIGN & READABILITY RULES ---
1. READABILITY IS PARAMOUNT:
   - Title cards are viewed from across the room on television screens (often displayed 5 thumbnails across a row).
   - Text must be large, bold, and commanding so it is effortlessly readable at a glance over photographic episode background images.
   - Never choose tiny, spindly decorative fonts or small sizes. Maintain generous sizing (title_font_size 95-130, subheading_font_size 38-52).

2. GRADIENT USAGE & PLACEMENT:
   - The rendering engine applies a smooth, dark shadow gradient (black fading to transparent) directly behind the text area to guarantee contrast against bright or dynamic episode imagery.
   - "gradient_width_pct": Integer between 40 and 55.
   - "gradient_opacity_pct": Integer between 82 and 95.

3. TEXT COLORS & HIGH-CONTRAST PALETTE:
   - Because the gradient behind the text is a DARK SHADOW (black/charcoal fade), all text colors MUST have HIGH LUMINANCE AND CONTRAST against a dark background.
   - NEVER choose dark or low-contrast colors (e.g. navy, dark red, dark purple, forest green, dark gray, muddy brown).
   - "font_color": Must be high-luminance (e.g. crisp white "#FFFFFF", bright ivory "#FFF8E7", golden amber "#F4B84D", cyber cyan "#00E5FF", neon yellow "#FFD600").
   - "subheading_color": Must complement "font_color" while remaining crisp and readable (e.g. "#E5E7EB", "#D1D5DB", "#F4B84D").

4. STRICTLY PROHIBITED FONTS:
   - NEVER choose or suggest "Montserrat" under any circumstances for either title or subtitle. It renders far too thin and frail for TV displays. Prefer solid, punchy grotesque or condensed options like Inter, Barlow Condensed, Rubik, Oswald, Outfit, or matching the title font.

Return ONLY a JSON object with these exact keys:
- "font_family": Name of the selected open-source Google Font for the title.
- "subheading_font_family": Name of the selected complementary open-source Google Font for the subtitle.
- "title_font_size": Integer between 90 and 130 (default 108).
- "subheading_font_size": Integer between 36 and 54 (default 44).
- "font_color": High-luminance hex color code for the main episode title.
- "subheading_color": Complementary, readable hex color for season/episode text.
- "text_position": One of ["left_center", "left_bottom", "center_bottom", "right_center", "right_bottom", "top_left", "center"].
- "gradient_side": "left", "bottom", "right", or "top" (strictly matching text_position).
- "gradient_width_pct": Integer between 40 and 55.
- "gradient_opacity_pct": Integer between 82 and 95.
- "subheading_position": "above" or "below".
- "subheading_casing": "upper", "title", or "lower".
- "subheading_tracking": Integer between 0 and 6.
- "subheading_format": "s_pad_ep_num", "season_num_ep_num", "s_pad_e_pad", "season_word_ep_word", or "compact_pad".
- "subheading_icon": Separator character between season and episode (e.g. "•", "-", ":", "/", or "").
- "subheading_gap": Integer between 10 and 26 (default 14).
- "text_box_width_pct": Integer between 40 and 55 (default 46).
- "reasoning": 1-2 sentences explaining how the font choices, positioning, casing, tracking, and palette capture the show's aesthetic and poster identity.
"""

        try:
            from google.genai import types
            contents = [poster_img, prompt] if poster_img else prompt
            response = self._client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
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
            if "top" in text_pos and data.get("gradient_side") != "top":
                data["gradient_side"] = "top"
            elif "bottom" in text_pos and data.get("gradient_side") != "bottom":
                data["gradient_side"] = "bottom"
            elif "right" in text_pos and data.get("gradient_side") not in ("right", "bottom", "top"):
                data["gradient_side"] = "right"
            elif "left" in text_pos and data.get("gradient_side") not in ("left", "bottom", "top"):
                data["gradient_side"] = "left"

            # Defensive post-processing: font sizes bounds
            try:
                tfs = int(data.get("title_font_size", 108))
                data["title_font_size"] = max(50, min(180, tfs))
            except Exception:
                data["title_font_size"] = 108

            try:
                sfs = int(data.get("subheading_font_size", 52))
                data["subheading_font_size"] = max(24, min(85, sfs))
            except Exception:
                data["subheading_font_size"] = 52

            # Subheading font fallback
            if not data.get("subheading_font_family"):
                data["subheading_font_family"] = data.get("font_family", "Oswald")

            # Defensively intercept and purge Montserrat if suggested
            if "montserrat" in (data.get("subheading_font_family") or "").lower():
                data["subheading_font_family"] = data.get("font_family") if "montserrat" not in (data.get("font_family") or "").lower() else "Inter"
            if "montserrat" in (data.get("font_family") or "").lower():
                data["font_family"] = "Oswald"

            # Subheading position, casing, tracking, gap, width
            pos = str(data.get("subheading_position", "above")).lower()
            data["subheading_position"] = "below" if pos == "below" else "above"

            case = str(data.get("subheading_casing", "upper")).lower()
            data["subheading_casing"] = case if case in ("upper", "title", "lower") else "upper"

            try:
                data["subheading_tracking"] = max(0, min(8, int(data.get("subheading_tracking", 0))))
            except Exception:
                data["subheading_tracking"] = 0

            try:
                data["subheading_gap"] = max(4, min(48, int(data.get("subheading_gap", 16))))
            except Exception:
                data["subheading_gap"] = 16

            try:
                data["text_box_width_pct"] = max(30, min(65, int(data.get("text_box_width_pct", 46))))
            except Exception:
                data["text_box_width_pct"] = 46

            fmt = str(data.get("subheading_format", "s_pad_ep_num")).strip()
            valid_fmts = ("s_pad_ep_num", "season_num_ep_num", "s_pad_ep_pad", "s_pad_e_pad", "season_word_ep_word", "compact_pad")
            data["subheading_format"] = fmt if fmt in valid_fmts else "s_pad_ep_num"

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
                "subheading_font_family": "Oswald",
                "font_color": "#FFFFFF",
                "subheading_color": "#D1D5DB",
                "gradient_side": "left",
                "gradient_width_pct": 48,
                "gradient_opacity_pct": 90,
                "subheading_icon": "•",
                "title_font_size": 108,
                "subheading_font_size": 52,
                "text_position": "left_center",
                "subheading_position": "above",
                "subheading_casing": "upper",
                "subheading_tracking": 0,
                "subheading_format": "s_pad_ep_num",
                "subheading_gap": 16,
                "text_box_width_pct": 46,
                "reasoning": user_msg
            }

