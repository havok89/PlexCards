import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont
import requests

from backend.config import FONTS_DIR

logger = logging.getLogger(__name__)

NUM_WORDS = {
    1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE", 
    6: "SIX", 7: "SEVEN", 8: "EIGHT", 9: "NINE", 10: "TEN",
    11: "ELEVEN", 12: "TWELVE", 13: "THIRTEEN", 14: "FOURTEEN", 15: "FIFTEEN",
    16: "SIXTEEN", 17: "SEVENTEEN", 18: "EIGHTEEN", 19: "NINETEEN", 20: "TWENTY"
}

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        try:
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4)) # type: ignore
        except ValueError:
            pass
    return (255, 255, 255)

class TitleCardRenderer:
    def __init__(self):
        self.fonts_dir = FONTS_DIR
        self.fonts_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_fonts()

    def _ensure_default_fonts(self):
        """Ensure standard fonts are cached."""
        default_fonts = {
            "Oswald": "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
            "Orbitron": "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
            "Bebas Neue": "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
            "Montserrat": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf"
        }
        for name, url in default_fonts.items():
            path = self.fonts_dir / f"{name.replace(' ', '')}.ttf"
            if not path.exists():
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        with open(path, "wb") as f:
                            f.write(r.content)
                except Exception as e:
                    logger.warning(f"Could not download font {name}: {e}")

    def get_font_path(self, font_family: str) -> Path:
        clean_name = font_family.replace(" ", "")
        local_path = self.fonts_dir / f"{clean_name}.ttf"
        if local_path.exists():
            return local_path
            
        for fallback in ["Montserrat.ttf", "Oswald.ttf", "BebasNeue.ttf"]:
            p = self.fonts_dir / fallback
            if p.exists():
                return p
                
        return Path("")

    def render(
        self,
        base_image_path: Path,
        episode_title: str,
        season_num: int,
        episode_num: int,
        style_config: Optional[Dict[str, Any]] = None
    ) -> Image.Image:
        """Render a title card with styled typography, positioning, and gradients."""
        style = style_config or {}
        text_pos = style.get("text_position", "left_center")
        font_family = style.get("font_family", "Montserrat")
        font_color = hex_to_rgb(style.get("font_color", "#FFFFFF"))
        sub_color = hex_to_rgb(style.get("subheading_color", "#A3A3A3"))
        
        # Determine gradient direction based on text position if not custom
        default_grad = "left"
        if "bottom" in text_pos:
            default_grad = "bottom"
        elif "right" in text_pos:
            default_grad = "right"
            
        grad_side = style.get("gradient_side", default_grad)
        grad_width_pct = style.get("gradient_width_pct", 50 if "bottom" in text_pos else 48)
        grad_opacity_pct = style.get("gradient_opacity_pct", 90)
        show_subheading = bool(style.get("show_subheading", 1))
        sub_icon = style.get("subheading_icon", "dot") # 'dot', 'delta', 'dash', 'none'
        
        # Load and resize base still to standard 1080p
        base_img = Image.open(base_image_path).convert("RGBA")
        base_img = base_img.resize((1920, 1080), Image.Resampling.LANCZOS)
        
        # 1. Apply Gradient
        gradient = self._create_gradient(grad_side, grad_width_pct, grad_opacity_pct)
        card = Image.alpha_composite(base_img, gradient)
        draw = ImageDraw.Draw(card)
        
        # 2. Setup Fonts
        font_path = self.get_font_path(font_family)
        if font_path.exists():
            sub_font = ImageFont.truetype(str(font_path), size=34)
            title_font = ImageFont.truetype(str(font_path), size=82)
        else:
            sub_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        # 3. Text Preparation
        s_word = NUM_WORDS.get(season_num, str(season_num))
        e_word = NUM_WORDS.get(episode_num, str(episode_num))
        season_part = f"SEASON {s_word}"
        episode_part = f"EPISODE {e_word}"
        
        # Layout metrics based on text_position
        margin_side = 110
        if "center_bottom" in text_pos:
            max_title_width = 1500
        else:
            max_title_width = int(1920 * (grad_width_pct / 100.0)) - margin_side - 30
        
        # Word wrap
        lines = []
        words = episode_title.upper().split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=title_font)
            if (bbox[2] - bbox[0]) > max_title_width:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)

        line_height = 92
        total_title_height = len(lines) * line_height

        # Compute Vertical Start Y
        if "center" in text_pos:
            start_y = 540 - (total_title_height // 2)
        else: # bottom
            bottom_baseline = 980
            start_y = bottom_baseline - total_title_height

        sub_y = start_y - 65

        # 4. Render Subheading
        if show_subheading:
            # Measure subheading components
            s_bbox = draw.textbbox((0, 0), season_part, font=sub_font)
            s_w = s_bbox[2] - s_bbox[0]
            e_bbox = draw.textbbox((0, 0), episode_part, font=sub_font)
            e_w = e_bbox[2] - e_bbox[0]
            
            icon_w = 20
            icon_gap = 18
            total_sub_w = s_w + icon_w + (icon_gap * 2) + e_w
            
            if text_pos == "center_bottom":
                sub_start_x = (1920 - total_sub_w) // 2
            elif "right" in text_pos:
                sub_start_x = 1920 - margin_side - total_sub_w
            else:
                sub_start_x = margin_side

            # Draw Season part
            draw.text((sub_start_x + 2, sub_y + 2), season_part, font=sub_font, fill=(0, 0, 0, 200))
            draw.text((sub_start_x, sub_y), season_part, font=sub_font, fill=sub_color)

            # Draw divider icon
            icon_x = sub_start_x + s_w + icon_gap
            if sub_icon == "delta":
                icon_h = 24
                icon_y = sub_y + 6
                delta_pts = [
                    (icon_x + icon_w / 2, icon_y),
                    (icon_x + icon_w, icon_y + icon_h),
                    (icon_x + icon_w / 2, icon_y + icon_h - 6),
                    (icon_x, icon_y + icon_h)
                ]
                shadow_pts = [(x + 2, y + 2) for x, y in delta_pts]
                draw.polygon(shadow_pts, fill=(0, 0, 0, 200))
                draw.polygon(delta_pts, fill=sub_color)
            elif sub_icon == "dot":
                dot_r = 4
                dot_cy = sub_y + 16
                draw.ellipse([(icon_x + 6 - dot_r + 2, dot_cy - dot_r + 2), (icon_x + 6 + dot_r + 2, dot_cy + dot_r + 2)], fill=(0, 0, 0, 200))
                draw.ellipse([(icon_x + 6 - dot_r, dot_cy - dot_r), (icon_x + 6 + dot_r, dot_cy + dot_r)], fill=sub_color)
            elif sub_icon == "dash":
                draw.line([(icon_x, sub_y + 16), (icon_x + 14, sub_y + 16)], fill=sub_color, width=3)

            # Draw Episode part
            ep_x = icon_x + icon_w + icon_gap
            draw.text((ep_x + 2, sub_y + 2), episode_part, font=sub_font, fill=(0, 0, 0, 200))
            draw.text((ep_x, sub_y), episode_part, font=sub_font, fill=sub_color)

        # 5. Render Title Lines
        for i, line in enumerate(lines):
            y = start_y + (i * line_height)
            line_bbox = draw.textbbox((0, 0), line, font=title_font)
            line_w = line_bbox[2] - line_bbox[0]
            
            if text_pos == "center_bottom":
                line_x = (1920 - line_w) // 2
            elif "right" in text_pos:
                line_x = 1920 - margin_side - line_w
            else:
                line_x = margin_side

            # Drop shadow
            draw.text((line_x + 3, y + 3), line, font=title_font, fill=(0, 0, 0, 220))
            draw.text((line_x, y), line, font=title_font, fill=font_color)

        return card.convert("RGB")

    def _create_gradient(self, side: str, width_pct: int, opacity_pct: int) -> Image.Image:
        """Create smooth alpha gradient for legibility."""
        gradient = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        draw = ImageDraw.Draw(gradient)
        max_alpha = int(255 * (opacity_pct / 100.0))
        
        if side == "left":
            grad_w = int(1920 * (width_pct / 100.0))
            for x in range(grad_w):
                progress = x / grad_w
                alpha = int(max_alpha * ((1 - progress) ** 1.4))
                draw.line([(x, 0), (x, 1080)], fill=(0, 0, 0, alpha))
        elif side == "right":
            grad_w = int(1920 * (width_pct / 100.0))
            start_x = 1920 - grad_w
            for x in range(start_x, 1920):
                progress = (1920 - x) / grad_w
                alpha = int(max_alpha * ((1 - progress) ** 1.4))
                draw.line([(x, 0), (x, 1080)], fill=(0, 0, 0, alpha))
        elif side == "bottom":
            grad_h = int(1080 * (width_pct / 100.0))
            start_y = 1080 - grad_h
            for y in range(start_y, 1080):
                progress = (1080 - y) / grad_h
                alpha = int(max_alpha * ((1 - progress) ** 1.4))
                draw.line([(0, y), (1920, y)], fill=(0, 0, 0, alpha))
                
        return gradient
