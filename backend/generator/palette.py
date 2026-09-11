import colorsys
from pathlib import Path
from typing import Union, List, Dict, Any, Tuple
from PIL import Image

def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) # type: ignore

def boost_luminance_for_text(rgb: Tuple[int, int, int], min_v: float = 0.85) -> str:
    """Takes an RGB color and ensures its value/brightness is high enough to be legible against dark backgrounds."""
    h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
    new_v = max(v, min_v)
    new_s = min(s, 0.75) # Keep saturated but not harsh
    r, g, b = colorsys.hsv_to_rgb(h, new_s, new_v)
    return rgb_to_hex((int(r * 255), int(g * 255), int(b * 255)))

def extract_palette(image_input: Union[str, Path, Image.Image]) -> Dict[str, Any]:
    """
    Extracts dominant, vibrant, and harmonious accent swatches from an image.
    Ultra-fast execution (<10ms) using downsampled box sampling and HSV scoring.
    """
    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input).convert("RGB")
    else:
        img = image_input.convert("RGB")

    # Downsample for lightning-fast histogram sampling
    small = img.resize((120, 120), Image.Resampling.BOX)
    pixels = small.getcolors(maxcolors=20000)

    if not pixels:
        return {
            "dominant": "#FFFFFF",
            "vibrant": "#F59E0B",
            "swatches": ["#FFFFFF", "#F59E0B", "#38BDF8", "#A3A3A3", "#E2E8F0"],
            "recommended": {
                "font_color": "#FFFFFF",
                "subheading_color": "#F59E0B"
            }
        }

    scored_colors = []
    for count, (r, g, b) in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        # Filter out near-pure blacks and washed-out pure whites
        if v < 0.20 or (s < 0.05 and v > 0.95):
            continue

        # Score balances saturation (vividness), brightness (visibility), and prominence
        vibrancy_score = (s ** 1.35) * (v ** 0.85) * (count ** 0.2)
        scored_colors.append((vibrancy_score, count, (r, g, b), h, s, v))

    scored_colors.sort(key=lambda x: x[0], reverse=True)

    # Pick 6 diverse colors with distinct hues/values
    chosen = []
    for score, count, (r, g, b), h, s, v in scored_colors:
        is_duplicate = False
        for cr, cg, cb in chosen:
            ch, cs, cv = colorsys.rgb_to_hsv(cr / 255.0, cg / 255.0, cb / 255.0)
            if abs(h - ch) < 0.07 and abs(v - cv) < 0.15:
                is_duplicate = True
                break
        if not is_duplicate:
            chosen.append((r, g, b))
            if len(chosen) >= 6:
                break

    # If too few unique colors found, pick top pixel counts
    if len(chosen) < 4:
        by_count = sorted(pixels, key=lambda x: x[0], reverse=True)
        for count, rgb in by_count:
            if rgb not in chosen and colorsys.rgb_to_hsv(rgb[0]/255, rgb[1]/255, rgb[2]/255)[2] > 0.25:
                chosen.append(rgb)
                if len(chosen) >= 5:
                    break

    swatches = [rgb_to_hex(c) for c in chosen]
    if not swatches:
        swatches = ["#FFFFFF", "#E2E8F0", "#F59E0B", "#38BDF8", "#A3A3A3"]

    # Select primary vibrant accent and legible text recommendation
    primary_vibrant = swatches[0]
    rec_title = boost_luminance_for_text(chosen[0], min_v=0.88) if chosen else "#FFFFFF"
    
    # For subheading: use a clean secondary accent or crisp neutral
    if len(chosen) > 1:
        rec_sub = boost_luminance_for_text(chosen[1], min_v=0.75)
    else:
        rec_sub = "#A3A3A3"

    return {
        "dominant": swatches[0],
        "vibrant": primary_vibrant,
        "swatches": swatches,
        "recommended": {
            "font_color": rec_title,
            "subheading_color": rec_sub
        }
    }
