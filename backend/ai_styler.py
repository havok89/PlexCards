import json
import logging
from typing import Dict, Any, Optional
from backend.config import GEMINI_API_KEY

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
                "font_color": "#F4B84D",
                "subheading_color": "#E5A93C",
                "gradient_side": "left",
                "gradient_width_pct": 48,
                "gradient_opacity_pct": 90,
                "subheading_icon": "•",
                "reasoning": "Default styling applied (Gemini key not configured)."
            }

        prompt = f"""
You are a graphic design expert specializing in title cards and television branding.
Analyze the following TV show and recommend the ideal title card typography and styling parameters:

Show: {show_title}
Genres: {', '.join(genres) if genres else 'Unknown'}
Overview: {overview[:300] if overview else 'N/A'}
User Style Direction: {user_prompt or 'Match the authentic tone, genre, and aesthetic of the series.'}

Return ONLY a JSON object with these exact keys:
- "font_family": The name of the best matching open-source font available (e.g. from Google Fonts / open repositories such as Montserrat, Oswald, Orbitron, Bebas Neue, Jost, Michroma, Bodoni Moda, Cinzel, Anton, Space Grotesk, Syne, Inter, Playfair Display, Cinzel Decorative, etc. If the show has an iconic proprietary font, provide the closest open-source equivalent). The server will automatically fetch it on the fly.
- "font_color": Hex color code for the main episode title (e.g. "#FFFFFF", "#F4B84D", "#00E5FF", "#E50914", "#E0E0E0")
- "subheading_color": Complementary hex color for season/episode text
- "text_position": One of ["left_center", "left_bottom", "center_bottom", "right_center", "right_bottom"]
- "gradient_side": "left", "bottom", or "right" (match the text_position: use "bottom" for bottom positions, "left" for left positions, "right" for right positions)
- "gradient_width_pct": Integer between 40 and 55
- "gradient_opacity_pct": Integer between 80 and 95
- "subheading_icon": A single character separator between season and episode text (e.g. "•", "-", ":", "|", ".", "/", "~", "=" or "" for none). NEVER suggest deltas or logos; always use a clean typographical character separator that complements the show's typography.
- "reasoning": 1 sentence explaining the creative design choice (mentioning the font match)
"""

        try:
            from google.genai import types
            response = self._client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    response_mime_type="application/json"
                )
            )
            raw_text = response.text.strip()
            data = json.loads(raw_text)
            return data
        except Exception as e:
            logger.error(f"Gemini style suggestion failed: {e}")
            return {
                "font_family": "Oswald",
                "font_color": "#F4B84D",
                "subheading_color": "#E5A93C",
                "gradient_side": "left",
                "gradient_width_pct": 48,
                "gradient_opacity_pct": 90,
                "subheading_icon": "dot",
                "reasoning": f"Fallback applied due to error: {e}"
            }
