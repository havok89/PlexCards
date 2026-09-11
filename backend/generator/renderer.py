import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
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
        """Ensure standard fallback and genre-diverse fonts are pre-cached."""
        default_font_urls = {
            "Oswald": "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
            "Orbitron": "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
            "Bebas Neue": "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf",
            "Cinzel": "https://github.com/google/fonts/raw/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
            "Anton": "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
            "Inter": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
            "Righteous": "https://github.com/google/fonts/raw/main/ofl/righteous/Righteous-Regular.ttf",
            "Playfair Display": "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
            "Space Grotesk": "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
            "Archivo Black": "https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf",
            "Syne": "https://github.com/google/fonts/raw/main/ofl/syne/Syne%5Bwght%5D.ttf",
            "Teko": "https://github.com/google/fonts/raw/main/ofl/teko/Teko%5Bwght%5D.ttf",
            "Michroma": "https://github.com/google/fonts/raw/main/ofl/michroma/Michroma-Regular.ttf",
            "Rubik": "https://github.com/google/fonts/raw/main/ofl/rubik/Rubik%5Bwght%5D.ttf",
            "Barlow Condensed": "https://github.com/google/fonts/raw/main/ofl/barlowcondensed/BarlowCondensed-Bold.ttf"
        }
        # Purge Montserrat if previously downloaded (too thin for title cards)
        (self.fonts_dir / "Montserrat.ttf").unlink(missing_ok=True)

        for name, url in default_font_urls.items():
            path = self.fonts_dir / f"{name.replace(' ', '')}.ttf"
            if not path.exists():
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        with open(path, "wb") as f:
                            f.write(r.content)
                        continue
                except Exception:
                    pass
                # Fallback to automated Google Fonts API download
                try:
                    self.download_open_source_font(name)
                except Exception as e:
                    logger.debug(f"Could not download font {name}: {e}")

    def download_open_source_font(self, font_name: str) -> Optional[Path]:
        """Automatically fetch any open-source font on-the-fly via Google Fonts API."""
        if not font_name or "montserrat" in font_name.lower():
            return None
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
        clean_name = (font_family or "").replace(" ", "").lower()
        if "montserrat" in clean_name:
            # Montserrat is explicitly disallowed (too thin for title cards); fall back to Inter
            return self.get_font_path("Inter")

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
        for fallback in ["Oswald.ttf", "BebasNeue.ttf", "Orbitron.ttf"]:
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
                if "montserrat" in name.lower():
                    continue
                if name.lower() not in seen:
                    seen.add(name.lower())
                    fonts.append({"name": name, "type": "custom", "filename": p.name})

        # Cached / standard fonts
        for ext in ["*.ttf", "*.otf"]:
            for p in self.fonts_dir.glob(ext):
                name = p.stem
                if "montserrat" in name.lower():
                    continue
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

        raw_fmt = (fmt_key or "season_num_ep_num").strip()
        fmt = raw_fmt.lower()

        if fmt in ("season_word_ep_word", "season {season_word} {icon} episode {episode_word}"):
            return f"SEASON {s_word}", f"EPISODE {e_word}", True
        elif fmt == "season_num_ep_num":
            return f"SEASON {s_num}", f"EPISODE {e_num}", True
        elif fmt in ("s_pad_ep_num", "s00_ep_num", "s_pad_episode_num", "s01 - episode 1", "s00 - episode 0", "s_pad_ep", "s01 • episode 1"):
            return f"S{s_pad}", f"EPISODE {e_num}", True
        elif fmt in ("s_pad_ep_pad", "s00_ep_pad", "s_pad_episode_pad", "s00 - episode 00", "s01 • episode 01"):
            return f"S{s_pad}", f"EPISODE {e_pad}", True
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
            if "{" in raw_fmt:
                try:
                    formatted = raw_fmt.format(
                        season=s_num,
                        s=s_num,
                        s_num=s_num,
                        season_pad=s_pad,
                        s_pad=s_pad,
                        season_word=s_word,
                        s_word=s_word,
                        episode=e_num,
                        e=e_num,
                        e_num=e_num,
                        episode_pad=e_pad,
                        e_pad=e_pad,
                        episode_word=e_word,
                        e_word=e_word,
                        icon="{icon}",
                        sep="{icon}"
                    )
                    if "{icon}" in formatted:
                        parts = formatted.split("{icon}", 1)
                        return parts[0].strip(), parts[1].strip(), True
                    return formatted.strip(), "", False
                except Exception:
                    pass
            return raw_fmt, "", False

    def render(
        self,
        base_image_path: Union[Path, str],
        episode_title: str,
        season_num: int,
        episode_num: int,
        style_config: Optional[Dict[str, Any]] = None,
        logo_image_path: Optional[Union[Path, str]] = None
    ) -> Image.Image:
        """Render a title card with styled typography, positioning, gradients, and cinematic FX."""
        style = style_config or {}
        text_pos = style.get("text_position", "left_center")
        font_family = style.get("font_family", "Oswald")
        sub_font_family = style.get("subheading_font_family") or font_family
        font_color = hex_to_rgb(style.get("font_color", "#FFFFFF"))
        sub_color = hex_to_rgb(style.get("subheading_color", "#A3A3A3"))
        
        # Determine positioning flags
        is_top = "top" in text_pos
        is_bottom = "bottom" in text_pos
        is_middle = not is_top and not is_bottom

        is_h_center = text_pos in ("center", "center_center", "middle_center") or ("center" in text_pos and (is_top or is_bottom))
        is_h_right = "right" in text_pos
        is_h_left = not is_h_center and not is_h_right

        # Determine gradient direction based on text position if not custom
        default_grad = "left"
        if is_top:
            default_grad = "top"
        elif is_bottom:
            default_grad = "bottom"
        elif is_h_right:
            default_grad = "right"
        elif is_h_center:
            default_grad = "center"
            
        grad_side = style.get("gradient_side", default_grad)
        grad_width_pct = style.get("gradient_width_pct", 50 if (is_bottom or is_top) else 48)
        grad_opacity_pct = style.get("gradient_opacity_pct", 90)
        show_subheading = bool(style.get("show_subheading", 1))
        sub_icon = style.get("subheading_icon", "dot")
        sub_fmt = style.get("subheading_format", "season_num_ep_num")
        title_font_size = int(style.get("title_font_size") or 108)
        sub_font_size = int(style.get("subheading_font_size") or 52)
        sub_gap = int(style.get("subheading_gap") if style.get("subheading_gap") is not None else 16)

        # Cinematic FX settings
        frosted_blur_pct = int(style.get("frosted_blur_pct", 0) or 0)
        film_grain_pct = int(style.get("film_grain_pct", 0) or 0)
        vignette_pct = int(style.get("vignette_pct", 0) or 0)
        text_shadow_mode = str(style.get("text_shadow_mode", "subtle") or "subtle").lower()
        show_logo = bool(style.get("show_logo", 0))
        logo_pos = str(style.get("logo_position", "top_right") or "top_right").lower()
        logo_opacity_pct = int(style.get("logo_opacity_pct", 80) or 80)
        logo_monochrome = bool(style.get("logo_monochrome", 1))

        # 3. Text Preparation & Width Calculation
        # Layout metrics based on text_position and text_box_width_pct
        margin_side = 110
        custom_tb_pct = style.get("text_box_width_pct")
        if custom_tb_pct:
            max_title_width = int(1920 * (int(custom_tb_pct) / 100.0))
            if not is_h_center and grad_side in ("left", "right"):
                min_grad = int(((max_title_width + margin_side + 40) / 1920.0) * 100)
                grad_width_pct = max(grad_width_pct, min_grad)
        elif is_h_center:
            max_title_width = 1500
        else:
            max_title_width = int(1920 * (grad_width_pct / 100.0)) - margin_side - 30
        
        # Load and resize base still to standard 1080p
        base_img = Image.open(base_image_path).convert("RGBA")
        base_img = base_img.resize((1920, 1080), Image.Resampling.LANCZOS)
        
        # Create Gradient overlay
        gradient = self._create_gradient(grad_side, grad_width_pct, grad_opacity_pct)

        # 1. Apply Frosted Glass Selective Blur (softly blurs still underneath the gradient)
        if frosted_blur_pct > 0:
            blur_radius = max(2, int((min(50, frosted_blur_pct) / 100.0) * 35))
            blurred_base = base_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            grad_alpha = gradient.split()[3]
            base_img = Image.composite(blurred_base, base_img, grad_alpha)

        # 2. Apply Perimeter Vignette
        if vignette_pct > 0:
            v_opacity = int(255 * (min(50, vignette_pct) / 100.0))
            vmask_full = Image.new("L", (1920, 1080), v_opacity)
            vmask_inner = Image.new("L", (1920, 1080), 0)
            idraw = ImageDraw.Draw(vmask_inner)
            idraw.ellipse([(110, 60), (1920 - 110, 1080 - 60)], fill=255)
            vmask_inner = vmask_inner.filter(ImageFilter.GaussianBlur(radius=120))
            vmask_final = ImageChops.subtract(vmask_full, vmask_inner)
            vignette = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            vignette.putalpha(vmask_final)
            base_img = Image.alpha_composite(base_img, vignette)

        # 3. Composite Gradient
        card = Image.alpha_composite(base_img, gradient)
        draw = ImageDraw.Draw(card)
        
        # 4. Setup Fonts
        font_path = self.get_font_path(font_family)
        if font_path.exists():
            title_font = ImageFont.truetype(str(font_path), size=title_font_size)
        else:
            title_font = ImageFont.load_default()

        if sub_font_family == font_family and font_path.exists():
            sub_font = ImageFont.truetype(str(font_path), size=sub_font_size)
        else:
            sub_font_path = self.get_font_path(sub_font_family)
            if sub_font_path.exists():
                sub_font = ImageFont.truetype(str(sub_font_path), size=sub_font_size)
            else:
                sub_font = ImageFont.truetype(str(font_path), size=sub_font_size) if font_path.exists() else ImageFont.load_default()
        
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
        
        # Layout subtitle metrics
        sub_height = int(sub_font_size * 1.2) if show_subheading else 0
        sub_pos_mode = style.get("subheading_position", "above") # 'above' or 'below'
        sub_tracking = int(style.get("subheading_tracking", 0) or 0)
        sub_casing = style.get("subheading_casing", "upper") # 'upper', 'title', 'lower'

        total_block_height = total_title_height
        if show_subheading:
            total_block_height += sub_gap + sub_height

        # Vertical alignment
        if is_middle:
            start_y = (1080 - total_block_height) // 2
        elif is_bottom:
            margin_bottom = 120
            start_y = 1080 - margin_bottom - total_block_height
        else: # is_top
            margin_top = 100
            start_y = margin_top

        # Subtitle positioning
        if sub_pos_mode == "below":
            sub_y = start_y + total_title_height + sub_gap
        else: # 'above'
            sub_y = start_y
            start_y = start_y + sub_height + sub_gap

        # Optional soft shadow / glow FX layer
        fx_layer = None
        fx_draw = None
        if text_shadow_mode in ("cinematic", "glow"):
            fx_layer = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            fx_draw = ImageDraw.Draw(fx_layer)

        def draw_tracked_text_to(target_draw, pos: Tuple[int, int], text: str, font, fill, tracking: int = 0):
            x, y = pos
            if tracking <= 0:
                target_draw.text((x, y), text, font=font, fill=fill)
                return
            for char in text:
                target_draw.text((x, y), char, font=font, fill=fill)
                char_bbox = target_draw.textbbox((0, 0), char, font=font)
                char_w = char_bbox[2] - char_bbox[0]
                x += char_w + tracking

        # 5. Render Subheading if enabled
        if show_subheading:
            season_part, episode_part, draw_sep = self.get_subheading_parts(season_num, episode_num, sub_fmt)
            
            def apply_casing(txt: str) -> str:
                if not txt:
                    return ""
                if sub_casing == "lower":
                    return txt.lower()
                elif sub_casing == "title":
                    return txt.title()
                return txt.upper()

            season_part = apply_casing(season_part)
            episode_part = apply_casing(episode_part)

            icon_map = {"dot": "•", "delta": "▲", "dash": "-", "slash": "/", "none": ""}
            sep_char = icon_map.get(sub_icon, sub_icon) if sub_icon else "•"

            def measure_tracked_width(text: str, font, tracking: int) -> int:
                if not text:
                    return 0
                if tracking <= 0:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    return bbox[2] - bbox[0]
                w = 0
                for char in text:
                    bbox = draw.textbbox((0, 0), char, font=font)
                    w += (bbox[2] - bbox[0]) + tracking
                return max(0, w - tracking)

            s_w = measure_tracked_width(season_part, sub_font, sub_tracking)
            e_w = measure_tracked_width(episode_part, sub_font, sub_tracking)
            
            sep_bbox = draw.textbbox((0, 0), sep_char, font=sub_font)
            sep_w = (sep_bbox[2] - sep_bbox[0]) if draw_sep and sep_char else 0
            gap = int(sub_font_size * 0.35)

            if season_part and episode_part:
                total_sub_w = s_w + gap + (sep_w + gap if draw_sep and sep_char else 0) + e_w
            elif season_part:
                total_sub_w = s_w
            elif episode_part:
                total_sub_w = e_w
            else:
                total_sub_w = 0

            if total_sub_w > 0:
                if is_h_center:
                    sub_start_x = (1920 - total_sub_w) // 2
                elif is_h_right:
                    sub_start_x = 1920 - margin_side - total_sub_w
                else:
                    sub_start_x = margin_side

                curr_x = sub_start_x

                # Draw Season shadow/glow
                if season_part:
                    if text_shadow_mode == "cinematic" and fx_draw:
                        draw_tracked_text_to(fx_draw, (curr_x + 3, sub_y + 3), season_part, font=sub_font, fill=(0, 0, 0, 210), tracking=sub_tracking)
                    elif text_shadow_mode == "glow" and fx_draw:
                        fx_draw.text((curr_x, sub_y), season_part, font=sub_font, fill=sub_color + (160,))
                    elif text_shadow_mode == "subtle":
                        draw_tracked_text_to(draw, (curr_x + 2, sub_y + 2), season_part, font=sub_font, fill=(0, 0, 0, 200), tracking=sub_tracking)
                    curr_x += s_w

                # Separator
                if season_part and episode_part:
                    curr_x += gap
                    if draw_sep and sep_char:
                        if text_shadow_mode == "cinematic" and fx_draw:
                            fx_draw.text((curr_x + 3, sub_y + 3), sep_char, font=sub_font, fill=(0, 0, 0, 210))
                        elif text_shadow_mode == "glow" and fx_draw:
                            fx_draw.text((curr_x, sub_y), sep_char, font=sub_font, fill=sub_color + (160,))
                        elif text_shadow_mode == "subtle":
                            draw.text((curr_x + 2, sub_y + 2), sep_char, font=sub_font, fill=(0, 0, 0, 200))
                        curr_x += sep_w + gap

                # Episode shadow/glow
                if episode_part:
                    if text_shadow_mode == "cinematic" and fx_draw:
                        draw_tracked_text_to(fx_draw, (curr_x + 3, sub_y + 3), episode_part, font=sub_font, fill=(0, 0, 0, 210), tracking=sub_tracking)
                    elif text_shadow_mode == "glow" and fx_draw:
                        fx_draw.text((curr_x, sub_y), episode_part, font=sub_font, fill=sub_color + (160,))
                    elif text_shadow_mode == "subtle":
                        draw_tracked_text_to(draw, (curr_x + 2, sub_y + 2), episode_part, font=sub_font, fill=(0, 0, 0, 200), tracking=sub_tracking)

        # 6. Render Title Shadows/Glow to fx_draw or draw
        title_positions = []
        for i, line in enumerate(lines):
            y = start_y + (i * line_height)
            line_bbox = draw.textbbox((0, 0), line, font=title_font)
            line_w = line_bbox[2] - line_bbox[0]
            
            if is_h_center:
                line_x = (1920 - line_w) // 2
            elif is_h_right:
                line_x = 1920 - margin_side - line_w
            else:
                line_x = margin_side

            title_positions.append((line_x, y, line))

            if text_shadow_mode == "cinematic" and fx_draw:
                fx_draw.text((line_x + 4, y + 4), line, font=title_font, fill=(0, 0, 0, 230))
            elif text_shadow_mode == "glow" and fx_draw:
                glow_col = font_color + (190,) if len(font_color) == 3 else font_color
                fx_draw.text((line_x, y), line, font=title_font, fill=glow_col)
            elif text_shadow_mode == "subtle":
                draw.text((line_x + 3, y + 3), line, font=title_font, fill=(0, 0, 0, 220))

        # Composite FX Layer (blurring soft shadow or glow)
        if fx_layer is not None:
            if text_shadow_mode == "cinematic":
                fx_layer = fx_layer.filter(ImageFilter.GaussianBlur(radius=5))
            elif text_shadow_mode == "glow":
                fx_layer = fx_layer.filter(ImageFilter.GaussianBlur(radius=12))
            card = Image.alpha_composite(card, fx_layer)
            draw = ImageDraw.Draw(card)

        # 7. Render Main Sharp Subtitle
        if show_subheading and total_sub_w > 0:
            curr_x = sub_start_x
            if season_part:
                draw_tracked_text_to(draw, (curr_x, sub_y), season_part, font=sub_font, fill=sub_color, tracking=sub_tracking)
                curr_x += s_w
            if season_part and episode_part:
                curr_x += gap
                if draw_sep and sep_char:
                    draw.text((curr_x, sub_y), sep_char, font=sub_font, fill=sub_color)
                    curr_x += sep_w + gap
            if episode_part:
                draw_tracked_text_to(draw, (curr_x, sub_y), episode_part, font=sub_font, fill=sub_color, tracking=sub_tracking)

        # 8. Render Main Sharp Title Lines
        for line_x, y, line in title_positions:
            draw.text((line_x, y), line, font=title_font, fill=font_color)

        # 9. Show Logo Watermark Overlay
        if show_logo and logo_image_path and Path(logo_image_path).exists():
            try:
                logo_img = Image.open(logo_image_path).convert("RGBA")
                max_logo_w, max_logo_h = 360, 130
                logo_ratio = min(max_logo_w / logo_img.width, max_logo_h / logo_img.height)
                new_w = max(1, int(logo_img.width * logo_ratio))
                new_h = max(1, int(logo_img.height * logo_ratio))
                logo_resized = logo_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                if logo_monochrome:
                    r, g, b, a = logo_resized.split()
                    white_img = Image.new("RGB", logo_resized.size, (255, 255, 255))
                    logo_resized = Image.merge("RGBA", (*white_img.split(), a))

                if logo_opacity_pct < 100:
                    alpha = Image.eval(logo_resized.split()[3], lambda p: int(p * (max(10, min(100, logo_opacity_pct)) / 100.0)))
                    logo_resized.putalpha(alpha)

                margin_x, margin_y = 85, 75
                if logo_pos == "top_left":
                    logo_x, logo_y = margin_x, margin_y
                elif logo_pos == "bottom_right":
                    logo_x = 1920 - new_w - margin_x
                    logo_y = 1080 - new_h - margin_y
                elif logo_pos == "bottom_left":
                    logo_x = margin_x
                    logo_y = 1080 - new_h - margin_y
                else: # top_right
                    logo_x = 1920 - new_w - margin_x
                    logo_y = margin_y

                logo_canvas = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
                logo_canvas.paste(logo_resized, (logo_x, logo_y), logo_resized)
                card = Image.alpha_composite(card, logo_canvas)
            except Exception as e:
                logger.warning(f"Could not render show logo badge: {e}")

        # 10. Film Grain Texture Overlay
        if film_grain_pct > 0:
            w_tile, h_tile = 480, 270
            raw_noise = os.urandom(w_tile * h_tile)
            grain_tile = Image.frombytes("L", (w_tile, h_tile), raw_noise).resize((1920, 1080), Image.Resampling.BILINEAR)
            alpha_scale = (min(25, film_grain_pct) / 100.0) * 1.8
            grain_alpha = Image.eval(grain_tile, lambda p: int(abs(p - 128) * alpha_scale))
            grain_layer = Image.new("RGBA", (1920, 1080), (255, 255, 255, 0))
            grain_layer.putalpha(grain_alpha)
            card = Image.alpha_composite(card, grain_layer)

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
        elif side == "top":
            grad_h = int(1080 * (width_pct / 100.0))
            for y in range(grad_h):
                progress = y / grad_h
                alpha = int(max_alpha * ((1 - progress) ** 1.4))
                draw.line([(0, y), (1920, y)], fill=(0, 0, 0, alpha))
        elif side in ("center", "radial", "middle"):
            from PIL import ImageFilter
            mask = Image.new("L", (1920, 1080), 0)
            mdraw = ImageDraw.Draw(mask)
            rx = int(960 * (width_pct / 100.0))
            ry = int(540 * (width_pct / 100.0))
            mdraw.ellipse([(960 - rx, 540 - ry), (960 + rx, 540 + ry)], fill=max_alpha)
            mask = mask.filter(ImageFilter.GaussianBlur(radius=70))
            gradient.paste((0, 0, 0, 255), (0, 0, 1920, 1080), mask=mask)
                
        return gradient
