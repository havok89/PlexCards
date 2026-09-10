import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont
import requests

from backend.config import FONTS_DIR, CUSTOM_FONTS_DIR
import re
from urllib.parse import quote

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
        self.custom_fonts_dir = CUSTOM_FONTS_DIR
        self.fonts_dir.mkdir(parents=True, exist_ok=True)
        self.custom_fonts_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_fonts()

    def _ensure_default_fonts(self):
        """Ensure standard fallback fonts are cached."""
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

    def download_open_source_font(self, font_name: str) -> Optional[Path]:
        """Automatically fetch any open-source font on-the-fly via Google Fonts API."""
        clean_name = font_name.replace(" ", "")
        target_path = self.fonts_dir / f"{clean_name}.ttf"
        if target_path.exists():
            return target_path

        encoded_name = quote(font_name)
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        candidate_urls = [
            f"https://fonts.googleapis.com/css2?family={encoded_name}:wght@700",
            f"https://fonts.googleapis.com/css2?family={encoded_name}"
        ]
        for css_url in candidate_urls:
            try:
                r = requests.get(css_url, headers=headers, timeout=8)
                if r.status_code == 200:
                    match = re.search(r'src:\s*url\((https://[^)]+)\)', r.text)
                    if match:
                        font_url = match.group(1)
                        font_res = requests.get(font_url, timeout=10)
                        if font_res.status_code == 200:
                            with open(target_path, "wb") as f:
                                f.write(font_res.content)
                            logger.info(f"✓ Automatically downloaded open-source font '{font_name}' to {target_path}")
                            return target_path
            except Exception as e:
                logger.warning(f"Could not auto-download font '{font_name}' from {css_url}: {e}")
        return None

    def get_font_path(self, font_family: str) -> Path:
        """Find font in custom_fonts/ or cache/fonts/, or auto-download if open-source."""
        clean_name = font_family.replace(" ", "").lower()

        # 1. Check custom_fonts/ for .ttf or .otf (user-supplied)
        for ext in [".ttf", ".otf"]:
            for f in self.custom_fonts_dir.glob(f"*{ext}"):
                if f.stem.replace(" ", "").lower() == clean_name:
                    return f

        # 2. Check cache/fonts/ for .ttf or .otf
        for ext in [".ttf", ".otf"]:
            for f in self.fonts_dir.glob(f"*{ext}"):
                if f.stem.replace(" ", "").lower() == clean_name:
                    return f

        # 3. Attempt automated on-demand download
        downloaded = self.download_open_source_font(font_family)
        if downloaded and downloaded.exists():
            return downloaded

        # 4. Fallback to standard clean font
        for fallback in ["Montserrat.ttf", "Oswald.ttf", "BebasNeue.ttf"]:
            p = self.fonts_dir / fallback
            if p.exists():
                return p

        return Path("")

    def get_available_fonts(self) -> List[Dict[str, Any]]:
        """Return list of all locally installed and cached fonts."""
        fonts = []
        seen = set()

        # Custom fonts
        for ext in ["*.ttf", "*.otf"]:
            for p in self.custom_fonts_dir.glob(ext):
                name = p.stem
                if name.lower() not in seen:
                    seen.add(name.lower())
                    fonts.append({"name": name, "type": "custom", "filename": p.name})

        # Cached / standard fonts
        for ext in ["*.ttf", "*.otf"]:
            for p in self.fonts_dir.glob(ext):
                name = p.stem
                if name.lower() not in seen:
                    seen.add(name.lower())
                    fonts.append({"name": name, "type": "open_source", "filename": p.name})

        fonts.sort(key=lambda x: x["name"])
        return fonts

    @staticmethod
    def get_subheading_parts(season_num: int, episode_num: int, fmt_key: str = "season_num_ep_num") -> Tuple[str, str, bool]:
        """
        Returns (season_part, episode_part, show_separator).
        If season_part or episode_part is empty, show_separator is False.
        """
        s_word = NUM_WORDS.get(season_num, str(season_num))
        e_word = NUM_WORDS.get(episode_num, str(episode_num))
        s_num = str(season_num)
        e_num = str(episode_num)
        s_pad = f"{season_num:02d}"
        e_pad = f"{episode_num:02d}"

        fmt = (fmt_key or "season_num_ep_num").strip().lower()

        if fmt in ("season_word_ep_word", "season {season_word} {icon} episode {episode_word}"):
            return f"SEASON {s_word}", f"EPISODE {e_word}", True
        elif fmt == "season_num_ep_num":
            return f"SEASON {s_num}", f"EPISODE {e_num}", True
        elif fmt in ("s_pad_e_pad", "s00_e00"):
            return f"S{s_pad}", f"E{e_pad}", True
        elif fmt in ("compact_pad", "s00e00"):
            return f"S{s_pad}E{e_pad}", "", False
        elif fmt in ("ep_num", "episode_num"):
            return "", f"EPISODE {e_num}", False
        elif fmt in ("ep_word", "episode_word"):
            return "", f"EPISODE {e_word}", False
        elif fmt in ("e_pad", "e00"):
            return "", f"E{e_pad}", False
        elif fmt in ("season_num",):
            return f"SEASON {s_num}", "", False
        elif fmt in ("season_word",):
            return f"SEASON {s_word}", "", False
        elif fmt in ("s_pad", "s00"):
            return f"S{s_pad}", "", False
        else:
            if "{" in fmt:
                try:
                    formatted = fmt.format(
                        season=s_num,
                        season_pad=s_pad,
                        season_word=s_word,
                        episode=e_num,
                        episode_pad=e_pad,
                        episode_word=e_word,
                        icon="{icon}"
                    )
                    if "{icon}" in formatted:
                        parts = formatted.split("{icon}", 1)
                        return parts[0].strip(), parts[1].strip(), True
                    return formatted.strip(), "", False
                except Exception:
                    pass
            return f"SEASON {s_num}", f"EPISODE {e_num}", True

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
        sub_icon = style.get("subheading_icon", "dot")
        sub_fmt = style.get("subheading_format", "season_num_ep_num")
        title_font_size = int(style.get("title_font_size") or 82)
        sub_font_size = int(style.get("subheading_font_size") or 34)
        
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
            sub_font = ImageFont.truetype(str(font_path), size=sub_font_size)
            title_font = ImageFont.truetype(str(font_path), size=title_font_size)
        else:
            sub_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        # 3. Text Preparation
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

        line_height = int(title_font_size * 1.12)
        total_title_height = len(lines) * line_height

        # Compute Vertical Start Y
        if "center" in text_pos:
            start_y = 540 - (total_title_height // 2)
        else: # bottom
            bottom_baseline = 980
            start_y = bottom_baseline - total_title_height

        sub_y = start_y - sub_font_size - int(title_font_size * 0.38)

        # 4. Render Subheading
        if show_subheading:
            season_part, episode_part, has_sep = self.get_subheading_parts(season_num, episode_num, sub_fmt)

            # Resolve separator character
            raw_icon = str(sub_icon).strip() if sub_icon else ""
            if raw_icon in ("dot", "bullet", "delta"):
                sep_char = "•"
            elif raw_icon == "dash":
                sep_char = "—"
            elif raw_icon == "none":
                sep_char = ""
            else:
                sep_char = raw_icon

            draw_sep = has_sep and bool(sep_char)

            gap = max(10, int(sub_font_size * 0.47))
            s_w = 0
            if season_part:
                s_bbox = draw.textbbox((0, 0), season_part, font=sub_font)
                s_w = s_bbox[2] - s_bbox[0]

            e_w = 0
            if episode_part:
                e_bbox = draw.textbbox((0, 0), episode_part, font=sub_font)
                e_w = e_bbox[2] - e_bbox[0]

            sep_w = 0
            if draw_sep:
                sep_bbox = draw.textbbox((0, 0), sep_char, font=sub_font)
                sep_w = sep_bbox[2] - sep_bbox[0]

            if season_part and episode_part:
                total_sub_w = s_w + gap + (sep_w + gap if draw_sep else 0) + e_w
            elif season_part:
                total_sub_w = s_w
            elif episode_part:
                total_sub_w = e_w
            else:
                total_sub_w = 0

            if total_sub_w > 0:
                if text_pos == "center_bottom":
                    sub_start_x = (1920 - total_sub_w) // 2
                elif "right" in text_pos:
                    sub_start_x = 1920 - margin_side - total_sub_w
                else:
                    sub_start_x = margin_side

                curr_x = sub_start_x

                # Draw Season part if present
                if season_part:
                    draw.text((curr_x + 2, sub_y + 2), season_part, font=sub_font, fill=(0, 0, 0, 200))
                    draw.text((curr_x, sub_y), season_part, font=sub_font, fill=sub_color)
                    curr_x += s_w

                # Draw separator if both parts present
                if season_part and episode_part:
                    curr_x += gap
                    if draw_sep:
                        draw.text((curr_x + 2, sub_y + 2), sep_char, font=sub_font, fill=(0, 0, 0, 200))
                        draw.text((curr_x, sub_y), sep_char, font=sub_font, fill=sub_color)
                        curr_x += sep_w + gap

                # Draw Episode part if present
                if episode_part:
                    draw.text((curr_x + 2, sub_y + 2), episode_part, font=sub_font, fill=(0, 0, 0, 200))
                    draw.text((curr_x, sub_y), episode_part, font=sub_font, fill=sub_color)

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
