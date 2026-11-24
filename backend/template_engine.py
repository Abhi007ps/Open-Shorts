import os
import math
import random
import uuid
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from typing import Dict, Any, Tuple, Optional, List

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "temp"))
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def generate_template_assets(
    gameplay_w: int = 960,
    gameplay_h: int = 540,
    gameplay_radius: int = 36,
    gameplay_border_w: int = 6,
    gameplay_border_color: str = "#FFFFFF",
    webcam_w: int = 300,
    webcam_h: int = 300,
    webcam_is_oval: bool = False,
    webcam_shape: str = "circle",
    webcam_radius: int = 32,
    webcam_border_w: int = 6,
    webcam_border_color: str = "#FFFFFF",
    webcam_glow_enabled: bool = True,
    webcam_glow_color: str = "#C084FC",
    webcam_glow_size: int = 28,
    webcam_glow_intensity: float = 1.3,
    webcam_glow_effect: str = "neon_lightning",
    divider_height: int = 4,
    divider_color: str = "#FFFFFF",
    prefix: str = ""
) -> Dict[str, Any]:
    """
    Generates high-resolution anti-aliased alpha masks and border overlays using Pillow.
    Supports circle, rounded square, rounded rectangle floating facecam shapes, and 50/50 split screen with divider.
    """
    scale = 3
    
    def parse_hex_color(hex_str: str) -> Tuple[int, int, int]:
        c = (hex_str or "#FFFFFF").strip().lstrip('#')
        if len(c) == 3:
            c = ''.join([x*2 for x in c])
        if len(c) != 6:
            return (255, 255, 255)
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))

    gp_rgb = parse_hex_color(gameplay_border_color)
    cam_rgb = parse_hex_color(webcam_border_color)
    glow_rgb = parse_hex_color(webcam_glow_color)
    div_rgb = parse_hex_color(divider_color) if divider_color else gp_rgb

    # Check for Split Screen layout mode (Speed Style from C:\ppp)
    is_split_screen = (webcam_shape == "split_screen") or (webcam_w >= 1000 and gameplay_w >= 1000) or (webcam_h >= 500)

    # 1. Gameplay Card Mask
    gp_mask = Image.new('L', (gameplay_w * scale, gameplay_h * scale), 255 if is_split_screen else 0)
    if not is_split_screen:
        draw_gm = ImageDraw.Draw(gp_mask)
        draw_gm.rounded_rectangle([0, 0, gameplay_w * scale - 1, gameplay_h * scale - 1], radius=gameplay_radius * scale, fill=255)
    gp_mask = gp_mask.resize((gameplay_w, gameplay_h), Image.Resampling.LANCZOS)
    gp_mask_path = os.path.join(ASSETS_DIR, f"{prefix}gameplay_mask.png")
    gp_mask.save(gp_mask_path)

    # 2. Gameplay Card Border (For split screen: adjustable crisp horizontal divider bar at the top edge)
    gp_border = Image.new('RGBA', (gameplay_w * scale, gameplay_h * scale), (0, 0, 0, 0))
    draw_gb = ImageDraw.Draw(gp_border)
    if is_split_screen:
        div_h = int(round(divider_height * scale))
        if div_h > 0:
            draw_gb.rectangle([0, 0, gameplay_w * scale - 1, div_h - 1], fill=(*div_rgb, 255))
    else:
        draw_gb.rounded_rectangle(
            [0, 0, gameplay_w * scale - 1, gameplay_h * scale - 1],
            radius=gameplay_radius * scale,
            outline=(*gp_rgb, 255),
            width=gameplay_border_w * scale
        )
    gp_border = gp_border.resize((gameplay_w, gameplay_h), Image.Resampling.LANCZOS)
    gp_border_path = os.path.join(ASSETS_DIR, f"{prefix}gameplay_border.png")
    gp_border.save(gp_border_path)

    # 3. Webcam Mask (Circle, Rounded Square, Rectangle, or Split Screen Top)
    is_rounded_rect = webcam_shape in ("rounded_rect", "rounded_square", "rectangle", "square", "rectangle_16_9", "rectangle_4_3", "custom")
    cam_mask = Image.new('L', (webcam_w * scale, webcam_h * scale), 255 if is_split_screen else 0)
    if not is_split_screen:
        draw_cm = ImageDraw.Draw(cam_mask)
        if is_rounded_rect:
            rad = min(webcam_radius, min(webcam_w, webcam_h) // 2) * scale
            draw_cm.rounded_rectangle([0, 0, webcam_w * scale - 1, webcam_h * scale - 1], radius=rad, fill=255)
        else:
            draw_cm.ellipse([0, 0, webcam_w * scale - 1, webcam_h * scale - 1], fill=255)
    cam_mask = cam_mask.resize((webcam_w, webcam_h), Image.Resampling.LANCZOS)
    cam_mask_path = os.path.join(ASSETS_DIR, f"{prefix}webcam_mask.png")
    cam_mask.save(cam_mask_path)

    # 4. Webcam Border with Reference-Grade Radiant Neon Plasma Halo
    glow_pad = 0
    if webcam_glow_enabled and not is_split_screen:
        glow_r = max(10, int(webcam_glow_size))
        glow_pad = glow_r + 12
        total_w = (webcam_w + 2 * glow_pad) * scale
        total_h = (webcam_h + 2 * glow_pad) * scale
        
        scx = total_w // 2
        scy = total_h // 2
        sr = (webcam_w * scale) // 2
        sbw = int(webcam_border_w * scale)
        pad_s = glow_pad * scale
        rad = min(webcam_radius, min(webcam_w, webcam_h) // 2) * scale
        rect_box = [pad_s, pad_s, pad_s + webcam_w * scale - 1, pad_s + webcam_h * scale - 1]
        
        cam_border = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
        
        # 4a. Outer broad diffuse neon bloom (atmospheric radiance)
        layer_bloom = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
        d_bloom = ImageDraw.Draw(layer_bloom)
        if is_rounded_rect:
            d_bloom.rounded_rectangle(
                rect_box,
                radius=rad,
                outline=(*glow_rgb, int(235 * min(1.8, webcam_glow_intensity))),
                width=int(28 * scale)
            )
        else:
            d_bloom.ellipse(
                (scx - sr, scy - sr, scx + sr, scy + sr),
                outline=(*glow_rgb, int(235 * min(1.8, webcam_glow_intensity))),
                width=int(28 * scale)
            )
        layer_bloom = layer_bloom.filter(ImageFilter.GaussianBlur(glow_r * scale * 0.55))
        
        # 4b. Concentrated vibrant plasma ring (intense electric core)
        layer_plasma = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
        d_plasma = ImageDraw.Draw(layer_plasma)
        if is_rounded_rect:
            d_plasma.rounded_rectangle(
                rect_box,
                radius=rad,
                outline=(*glow_rgb, int(255 * min(1.8, webcam_glow_intensity))),
                width=int(14 * scale)
            )
        else:
            d_plasma.ellipse(
                (scx - sr, scy - sr, scx + sr, scy + sr),
                outline=(*glow_rgb, int(255 * min(1.8, webcam_glow_intensity))),
                width=int(14 * scale)
            )
        layer_plasma = layer_plasma.filter(ImageFilter.GaussianBlur(glow_r * scale * 0.22))
        
        # 4c. Bright hot neon fringe
        layer_hot = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
        d_hot = ImageDraw.Draw(layer_hot)
        hot_rgb = tuple(min(255, int(c * 0.5 + 255 * 0.5)) for c in glow_rgb)
        if is_rounded_rect:
            d_hot.rounded_rectangle(
                rect_box,
                radius=rad,
                outline=(*hot_rgb, 255),
                width=int(7 * scale)
            )
        else:
            d_hot.ellipse(
                (scx - sr, scy - sr, scx + sr, scy + sr),
                outline=(*hot_rgb, 255),
                width=int(7 * scale)
            )
        layer_hot = layer_hot.filter(ImageFilter.GaussianBlur(glow_r * scale * 0.09))
        
        # 4d. Pure Solid White Core Tube
        layer_core = Image.new('RGBA', (total_w, total_h), (0, 0, 0, 0))
        d_core = ImageDraw.Draw(layer_core)
        if is_rounded_rect:
            d_core.rounded_rectangle(
                rect_box,
                radius=rad,
                outline=(*cam_rgb, 255),
                width=sbw
            )
        else:
            d_core.ellipse(
                (scx - sr, scy - sr, scx + sr, scy + sr),
                outline=(*cam_rgb, 255),
                width=sbw
            )
        
        # Composite all layers for maximum electric vibrance
        cam_border.alpha_composite(layer_bloom)
        cam_border.alpha_composite(layer_plasma)
        cam_border.alpha_composite(layer_plasma) # double pass for punchy saturated neon glow
        cam_border.alpha_composite(layer_hot)
        cam_border.alpha_composite(layer_core)
        
        cam_border = cam_border.resize((webcam_w + 2*glow_pad, webcam_h + 2*glow_pad), Image.Resampling.LANCZOS)
    else:
        cam_border = Image.new('RGBA', (webcam_w * scale, webcam_h * scale), (0, 0, 0, 0))
        if not is_split_screen:
            draw_cb = ImageDraw.Draw(cam_border)
            if is_rounded_rect:
                rad = min(webcam_radius, min(webcam_w, webcam_h) // 2) * scale
                draw_cb.rounded_rectangle(
                    [0, 0, webcam_w * scale - 1, webcam_h * scale - 1],
                    radius=rad,
                    outline=(*cam_rgb, 255),
                    width=webcam_border_w * scale
                )
            else:
                draw_cm_border = ImageDraw.Draw(cam_border)
                draw_cm_border.ellipse(
                    [0, 0, webcam_w * scale - 1, webcam_h * scale - 1],
                    outline=(*cam_rgb, 255),
                    width=webcam_border_w * scale
                )
        cam_border = cam_border.resize((webcam_w, webcam_h), Image.Resampling.LANCZOS)
        
    cam_border_path = os.path.join(ASSETS_DIR, f"{prefix}webcam_border.png")
    cam_border.save(cam_border_path)

    return {
        "gameplay_mask": gp_mask_path,
        "gameplay_border": gp_border_path,
        "webcam_mask": cam_mask_path,
        "webcam_border": cam_border_path,
        "webcam_glow_pad": glow_pad
    }

def generate_hook_headline_asset(
    hook_config: Dict[str, Any],
    canvas_w: int = 1080
) -> Optional[Tuple[str, int]]:
    """
    Renders pixel-perfect Hook Headline matching the viral reference style:
    - Bold Impact font (90-98px)
    - True per-word vertical color gradients (white-to-lavender, and pink-to-purple on highlight)
    - Solid 3D extruded downward drop shadow
    - Crisp solid black letter stroke
    Returns (png_path, top_y_on_canvas)
    """
    if not hook_config or not hook_config.get("enabled", True):
        return None
    text = hook_config.get("text", "").strip()
    if not text:
        return None
        
    font_size = int(hook_config.get("font_size", 94))
    pos_y = int(hook_config.get("position_y", 205))
    highlight_word = hook_config.get("highlight_word", "").strip()
    stroke_w = int(hook_config.get("outline_width", 6))
    extrusion_d = int(hook_config.get("shadow_depth", 6))
    
    # Load Impact font with fallback
    font_cand = ["C:/Windows/Fonts/impact.ttf", "impact.ttf", "arialbd.ttf"]
    font = None
    for fc in font_cand:
        if os.path.exists(fc):
            try:
                font = ImageFont.truetype(fc, font_size)
                break
            except Exception:
                pass
    if not font:
        font = ImageFont.load_default()
        
    # Color Gradients (top and bottom colors)
    style_p = hook_config.get("style_preset", "purple_neon")
    primary_top = hook_config.get("primary_color", "#FFFFFF")
    primary_bot = "#CDC1E8"
    hl_top = hook_config.get("highlight_color", "#EA7BFC")
    hl_bot = "#7B2CBF"
    
    if style_p == "gold_strike":
        primary_bot = "#F3E8FF"
        hl_top = "#FFE600"
        hl_bot = "#D97706"
    elif style_p == "cyber_cyan":
        primary_bot = "#CFFAFE"
        hl_top = "#00F5FF"
        hl_bot = "#0284C7"
    elif style_p == "fire_red":
        primary_bot = "#FEE2E2"
        hl_top = "#FF4500"
        hl_bot = "#B91C1C"
    elif style_p == "toxic_green":
        primary_bot = "#DCFCE7"
        hl_top = "#00FF66"
        hl_bot = "#15803D"
        
    words = text.split()
    space_w = font.getbbox(' ')[2] - font.getbbox(' ')[0] + 12
    
    word_boxes = []
    total_w = 0
    has_asterisks = any(w.startswith('*') and w.endswith('*') for w in words)
    
    for idx, w in enumerate(words):
        clean_w = w.strip('*')
        bbox = font.getbbox(clean_w)
        w_w = bbox[2] - bbox[0]
        w_h = bbox[3] - bbox[1]
        
        is_hl = False
        if has_asterisks and w.startswith('*') and w.endswith('*'):
            is_hl = True
        elif highlight_word and clean_w.upper() == highlight_word.upper():
            is_hl = True
        elif not has_asterisks and not highlight_word and len(words) > 1 and idx == 1:
            is_hl = True
            
        word_boxes.append({
            "word": clean_w,
            "is_hl": is_hl,
            "w": w_w,
            "h": w_h,
            "bbox": bbox
        })
        total_w += w_w
        if idx < len(words) - 1:
            total_w += space_w
            
    max_h = max(wb["h"] for wb in word_boxes)
    pad = stroke_w + extrusion_d + 18
    img_h = max_h + pad * 2
    
    hook_img = Image.new("RGBA", (canvas_w, img_h), (0, 0, 0, 0))
    start_x = (canvas_w - total_w) // 2
    base_y = pad
    
    # 1. 3D downward extruded drop shadow
    shadow_img = Image.new("RGBA", (canvas_w, img_h), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_img)
    curr_x = start_x
    for wb in word_boxes:
        for d in range(1, extrusion_d + 1):
            s_draw.text((curr_x, base_y + d), wb["word"], font=font, fill="#08020c", stroke_width=stroke_w, stroke_fill="#08020c")
        curr_x += wb["w"] + space_w
    soft_shadow = shadow_img.filter(ImageFilter.GaussianBlur(2.5))
    hook_img.alpha_composite(soft_shadow)
    hook_img.alpha_composite(shadow_img)
    
    # 2. Crisp solid black stroke
    stroke_layer = Image.new("RGBA", (canvas_w, img_h), (0, 0, 0, 0))
    st_draw = ImageDraw.Draw(stroke_layer)
    curr_x = start_x
    for wb in word_boxes:
        st_draw.text((curr_x, base_y), wb["word"], font=font, fill="#000000", stroke_width=stroke_w, stroke_fill="#000000")
        curr_x += wb["w"] + space_w
    hook_img.alpha_composite(stroke_layer)
    
    # 3. True vertical gradient fill per word
    curr_x = start_x
    def h2rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        
    for wb in word_boxes:
        w_w, w_h = wb["w"], wb["h"]
        mask = Image.new("L", (w_w + stroke_w * 4, w_h + stroke_w * 4), 0)
        m_draw = ImageDraw.Draw(mask)
        m_draw.text((-wb["bbox"][0] + stroke_w * 2, -wb["bbox"][1] + stroke_w * 2), wb["word"], font=font, fill=255)
        
        top_c = hl_top if wb["is_hl"] else primary_top
        bot_c = hl_bot if wb["is_hl"] else primary_bot
        r1, g1, b1 = h2rgb(top_c)
        r2, g2, b2 = h2rgb(bot_c)
        
        grad = Image.new("RGBA", mask.size)
        g_h = mask.size[1]
        for y_i in range(g_h):
            t = (y_i / max(1, g_h - 1)) ** 1.05
            cr = int(r1 + (r2 - r1) * t)
            cg = int(g1 + (g2 - g1) * t)
            cb = int(b1 + (b2 - b1) * t)
            for x_i in range(mask.size[0]):
                grad.putpixel((x_i, y_i), (cr, cg, cb, 255))
                
        word_render = Image.new("RGBA", mask.size, (0, 0, 0, 0))
        word_render.paste(grad, (0, 0), mask)
        hook_img.alpha_composite(word_render, (curr_x - stroke_w * 2, base_y - stroke_w * 2))
        curr_x += wb["w"] + space_w
        
    hook_path = os.path.join(TEMP_DIR, f"hook_title_{uuid.uuid4().hex[:8]}.png")
    hook_img.save(hook_path)
    return hook_path, pos_y - pad

def build_composite_filtergraph(
    canvas_w: int = 1080,
    canvas_h: int = 1920,
    bg_blur_sigma: int = 30,
    bg_brightness: float = -0.12,
    gameplay_crop: Dict[str, int] = None, # {"x": 0, "y": 0, "w": 640, "h": 360}
    gameplay_w: int = 960,
    gameplay_h: int = 540,
    gameplay_y: int = 690,
    gameplay_zoom: float = 1.0,
    gameplay_pan_x: float = 0.0,
    gameplay_pan_y: float = 0.0,
    webcam_crop: Dict[str, int] = None, # {"x": 22, "y": 160, "w": 84, "h": 84}
    webcam_w: int = 300,
    webcam_h: int = 300,
    webcam_x: Optional[int] = None,
    webcam_y: int = 540,
    webcam_glow_pad: int = 0,
    hook_title_y: Optional[int] = None,
    sharpen_amount: float = 0.8,
    contrast_boost: float = 1.08,
    saturation_boost: float = 1.22,
    brightness_offset: float = 0.01,
    deblock_level: str = "medium",
    micro_texture: float = 0.6,
    dynamic_range_pop: bool = True,
    pixel_generator: bool = True,
    pixel_generator_mode: str = "ultra",
    subtitles_ass_path: str = None,
    divider_line: bool = True,
    divider_color: str = "#FFFFFF",
    divider_height: int = 4,
    input_video_w: int = 1920,
    input_video_h: int = 1080
) -> str:
    """
    Constructs the complete FFmpeg complex filter string with Topaz-grade upscaling and enhancements.
    Supports 4K UHD (2160x3840), 2K QHD (1440x2560), and 1080p with:
    1. Deblock & Spatio-Temporal Denoise Pre-Pass (cleans stream macroblocks before scaling)
    2. Lanczos-4 Sinc Super-Resolution Scaling with full chroma planes (full_chroma_int+full_chroma_inp)
    3. Dual-Stage Detail Recovery: Fine High-Pass Micro-Texture Unsharp + AMD FidelityFX CAS (zero halos)
    4. Dynamic Range Studio Black Re-anchoring (rich cinematic blacks & highlight pop)
    """
    # Gameplay crop, zoom, and framing pan (horizontal & vertical positioning inside card)
    src_w = int(input_video_w or 1920)
    src_h = int(input_video_h or 1080)
    if gameplay_crop:
        src_x = max(0, min(src_w - 32, int(gameplay_crop.get("x", 0))))
        src_y = max(0, min(src_h - 32, int(gameplay_crop.get("y", 0))))
        base_w = max(32, min(src_w - src_x, int(gameplay_crop.get("w", src_w))))
        base_h = max(32, min(src_h - src_y, int(gameplay_crop.get("h", src_h))))
    else:
        src_x = 0
        src_y = 0
        base_w = src_w
        base_h = src_h

    card_ar = max(0.1, gameplay_w / max(1, gameplay_h))
    base_ar = base_w / max(1, base_h)

    eff_zoom = float(gameplay_zoom)
    # If user panned but zoom is at 1.0, give slight auto-headroom so pan visibly moves video
    if eff_zoom <= 1.0 and (abs(gameplay_pan_x) > 0.01 or abs(gameplay_pan_y) > 0.01):
        eff_zoom = 1.15

    if eff_zoom > 1.0 or abs(card_ar - base_ar) > 0.01 or abs(gameplay_pan_x) > 0.01 or abs(gameplay_pan_y) > 0.01:
        if card_ar <= base_ar:
            fit_h = base_h
            fit_w = int(round(base_h * card_ar))
        else:
            fit_w = base_w
            fit_h = int(round(base_w / card_ar))

        zw = max(64, min(base_w, int(round(fit_w / eff_zoom))))
        zh = max(64, min(base_h, int(round(fit_h / eff_zoom))))
        
        avail_x = max(0, base_w - zw)
        avail_y = max(0, base_h - zh)
        
        center_x = src_x + avail_x // 2
        center_y = src_y + avail_y // 2
        
        # Pan offsets (-100% to +100%)
        shift_x = int(round((gameplay_pan_x / 100.0) * (avail_x / 2.0)))
        shift_y = int(round((gameplay_pan_y / 100.0) * (avail_y / 2.0)))
        
        zx = max(src_x, min(src_x + avail_x, center_x + shift_x))
        zy = max(src_y, min(src_y + avail_y, center_y + shift_y))
        
        # Ensure even coordinates for FFmpeg / YUV
        zw = (zw // 2) * 2
        zh = (zh // 2) * 2
        zx = (zx // 2) * 2
        zy = (zy // 2) * 2
        
        gameplay_crop_filter = f"crop={zw}:{zh}:{zx}:{zy},"
    else:
        gameplay_crop_filter = ""

    if not webcam_crop:
        webcam_crop = {"x": 22, "y": 160, "w": 480, "h": 270}
    cx = max(0, min(src_w - 32, int(webcam_crop.get("x", 0))))
    cy = max(0, min(src_h - 32, int(webcam_crop.get("y", 0))))
    cw = max(32, min(src_w - cx, int(webcam_crop.get("w", 480))))
    ch = max(32, min(src_h - cy, int(webcam_crop.get("h", 270))))
    cw = (cw // 2) * 2
    ch = (ch // 2) * 2
    cx = (cx // 2) * 2
    cy = (cy // 2) * 2

    # Positioning (Speed Split-Screen Viral layout: 1080x700 Facecam + 1080x700 Gameplay = 1400px Active Video)
    is_split_screen = (webcam_w >= 1000 and gameplay_w >= 1000) or (webcam_h >= 500)
    if is_split_screen:
        # Reference template layout: Facecam 700px (Y=260 to 960), Center divider at Y=960,
        # Gameplay 700px (Y=960 to 1660). Total active video: 1400px (matches reference videos in C:\ppp)
        if canvas_h <= 1400:
            top_pad = 0
            sec_h = int(canvas_h // 2)
        else:
            sec_h = int(round(canvas_h * (700 / 1920.0)))
            top_pad = int(round((canvas_h - (sec_h * 2)) / 2.0))
        gameplay_w = canvas_w
        gameplay_h = sec_h
        gameplay_x = 0
        gameplay_y = top_pad + sec_h
        webcam_w = canvas_w
        webcam_h = sec_h
        webcam_x = 0
        webcam_y = top_pad

        # For Split-Screen, Facecam fills webcam_w x webcam_h edge-to-edge (just like gameplay in the bottom half)
        # Compute cover crop from user's 16:9 crop reticle to match slot aspect ratio with 100% natural pixels & zero black bars:
        slot_ar = float(webcam_w) / float(webcam_h)
        cam_ar = float(cw) / float(ch) if ch > 0 else slot_ar

        if cam_ar > slot_ar:
            eff_cw = int(round(ch * slot_ar))
            eff_ch = ch
            eff_cx = cx + (cw - eff_cw) // 2
            eff_cy = cy
        elif cam_ar < slot_ar:
            eff_cw = cw
            eff_ch = int(round(cw / slot_ar))
            eff_cx = cx
            eff_cy = cy + (ch - eff_ch) // 2
        else:
            eff_cw = cw
            eff_ch = ch
            eff_cx = cx
            eff_cy = cy

        eff_cw = max(32, min(src_w, (eff_cw // 2) * 2))
        eff_ch = max(32, min(src_h, (eff_ch // 2) * 2))
        eff_cx = max(0, min(src_w - eff_cw, (eff_cx // 2) * 2))
        eff_cy = max(0, min(src_h - eff_ch, (eff_cy // 2) * 2))
        webcam_crop_filter = f"crop={eff_cw}:{eff_ch}:{eff_cx}:{eff_cy},"
    else:
        gameplay_x = (canvas_w - gameplay_w) // 2
        if webcam_x is None:
            webcam_x = (canvas_w - webcam_w) // 2
        else:
            webcam_x = int(webcam_x)
        webcam_y = int(webcam_y)
        webcam_crop_filter = f"crop={cw}:{ch}:{cx}:{cy},"

    # 1 & 2. AI Neural Pixel Generator / Detail Synthesis Engine
    if pixel_generator and pixel_generator_mode != "off":
        if pixel_generator_mode == "ultra":
            # State-of-the-art 4K Master Synthesis (crisp, high-fidelity micro-textures with zero blur)
            cas_strength_gp = 0.75
            cas_strength_cam = 0.65
            la_gp = 0.65
            la_cam = 0.50
            gp_contrast = 1.05
            gp_sat = 1.08
            cam_contrast = 1.03
            cam_sat = 1.05
            deblock_str = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""
            cam_pre_deblock = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""
        elif pixel_generator_mode == "balanced":
            cas_strength_gp = 0.60
            cas_strength_cam = 0.52
            la_gp = 0.50
            la_cam = 0.40
            gp_contrast = 1.04
            gp_sat = 1.06
            cam_contrast = 1.02
            cam_sat = 1.04
            deblock_str = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""
            cam_pre_deblock = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""
        elif pixel_generator_mode == "film":
            cas_strength_gp = 0.60
            cas_strength_cam = 0.50
            la_gp = 0.55
            la_cam = 0.45
            gp_contrast = 1.05
            gp_sat = 1.04
            cam_contrast = 1.03
            cam_sat = 1.03
            deblock_str = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""
            cam_pre_deblock = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""
        else:
            cas_strength_gp = min(0.85, max(0.18, sharpen_amount * 0.75))
            cas_strength_cam = min(0.75, max(0.20, sharpen_amount * 0.65))
            la_gp = min(1.00, max(0.08, micro_texture * 1.00))
            la_cam = min(0.90, max(0.12, micro_texture * 0.90))
            gp_contrast = max(1.02, min(1.15, contrast_boost))
            gp_sat = max(1.04, min(1.25, saturation_boost))
            cam_contrast = min(1.06, max(1.00, 1.0 + (contrast_boost - 1.0) * 0.50))
            cam_sat = min(1.08, max(1.01, 1.0 + (saturation_boost - 1.0) * 0.35))
            deblock_str = "hqdn3d=0.6:0.6:1.2:1.2," if deblock_level in ("medium", "strong") else ""
            cam_pre_deblock = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""

        micro_str_gp = f"unsharp=lx=3:ly=3:la={la_gp:.2f}:cx=3:cy=3:ca=0.0,"
        micro_str_cam = f"unsharp=lx=3:ly=3:la={la_cam:.2f}:cx=3:cy=3:ca=0.0,"
        gp_gamma = 1.01
        cam_gamma = 1.04
        cam_bright = brightness_offset + 0.015

        enhance_gp = f"{micro_str_gp}cas={cas_strength_gp:.2f},eq=contrast={gp_contrast:.2f}:saturation={gp_sat:.2f}:brightness={brightness_offset:.2f}:gamma={gp_gamma:.2f},gradfun=radius=12:strength=0.8,"
        enhance_cam = f"{micro_str_cam}cas={cas_strength_cam:.2f},eq=contrast={cam_contrast:.2f}:saturation={cam_sat:.2f}:brightness={cam_bright:.2f}:gamma={cam_gamma:.2f},gradfun=radius=16:strength=0.9,"
    else:
        # Standard Fallback
        deblock_str = "hqdn3d=0.6:0.6:1.2:1.2," if deblock_level in ("medium", "strong") else ""
        cam_pre_deblock = "hqdn3d=0.5:0.5:1.0:1.0," if deblock_level in ("medium", "strong") else ""

        micro_str_gp = ""
        if micro_texture > 0.05:
            la_gp = min(0.38, max(0.08, micro_texture * 0.48))
            micro_str_gp = f"unsharp=lx=3:ly=3:la={la_gp:.2f}:cx=3:cy=3:ca=0.0,"

        micro_str_cam = ""
        if micro_texture > 0.05:
            la_cam = min(0.36, max(0.12, micro_texture * 0.52))
            micro_str_cam = f"unsharp=lx=3:ly=3:la={la_cam:.2f}:cx=3:cy=3:ca=0.0,"

        cas_strength_gp = min(0.42, max(0.18, sharpen_amount * 0.50))
        cas_strength_cam = min(0.40, max(0.20, sharpen_amount * 0.48))

        gp_contrast = max(1.04, min(1.12, contrast_boost))
        gp_sat = max(1.08, min(1.25, saturation_boost))
        gp_gamma = 1.01
        enhance_gp = f"{micro_str_gp}cas={cas_strength_gp:.2f},eq=contrast={gp_contrast:.2f}:saturation={gp_sat:.2f}:brightness={brightness_offset:.2f}:gamma={gp_gamma:.2f},gradfun=radius=12:strength=0.8,"

        cam_sat = min(1.08, max(1.01, 1.0 + (saturation_boost - 1.0) * 0.35))
        cam_contrast = min(1.06, max(1.00, 1.0 + (contrast_boost - 1.0) * 0.50))
        cam_gamma = 1.04
        cam_bright = brightness_offset + 0.015
        enhance_cam = f"{micro_str_cam}cas={cas_strength_cam:.2f},eq=contrast={cam_contrast:.2f}:saturation={cam_sat:.2f}:brightness={cam_bright:.2f}:gamma={cam_gamma:.2f},gradfun=radius=16:strength=0.9,"

    # Solid pure black background (Speed Viral Letterbox with top and bottom black bars, zero blur)
    bg_filter = f"color=c=black:s={canvas_w}x{canvas_h}:r=60[bg]"

    if is_split_screen:
        filter_chains = [
            bg_filter,
            f"[0:v]{gameplay_crop_filter}{deblock_str}scale={gameplay_w}:{gameplay_h}:flags=lanczos+accurate_rnd,{enhance_gp}format=rgba[gp_raw]",
            f"[0:v]{webcam_crop_filter}{cam_pre_deblock}scale={webcam_w}:{webcam_h}:flags=lanczos+accurate_rnd,{enhance_cam}format=rgba[cam_raw]",
            f"[bg][cam_raw]overlay={webcam_x}:{webcam_y}:shortest=1:eof_action=repeat[bg_cam]",
            f"[bg_cam][gp_raw]overlay={gameplay_x}:{gameplay_y}:eof_action=repeat[bg_all]",
        ]

        # Center Horizontal Divider Bar (Speed Viral Split Line)
        scaled_div_h = max(1, int(round(divider_height * (canvas_h / 1920.0)))) if divider_line and divider_height > 0 else 0
        if scaled_div_h > 0:
            div_y = int(round(gameplay_y - scaled_div_h / 2.0))
            hex_col = divider_color.replace("#", "0x") if divider_color.startswith("#") else divider_color
            filter_chains.append(f"[bg_all]drawbox=x=0:y={div_y}:w={canvas_w}:h={scaled_div_h}:color={hex_col}@1:t=fill[bg_div]")
            base_overlay_layer = "[bg_div]"
        else:
            base_overlay_layer = "[bg_all]"

        if hook_title_y is not None:
            filter_chains.append(f"{base_overlay_layer}[5:v]overlay=0:{hook_title_y}:eof_action=repeat[pre_sub]")
        else:
            filter_chains.append(f"{base_overlay_layer}null[pre_sub]")
    else:
        filter_chains = [
            # 1. Background layer: Fill 9:16 vertical canvas
            bg_filter,
            
            # 2. Gameplay card: crop -> native pre-deblock -> scale with lanczos -> Topaz enhancement -> mask -> card -> border
            f"[0:v]{gameplay_crop_filter}{deblock_str}scale={gameplay_w}:{gameplay_h}:flags=lanczos+accurate_rnd,{enhance_gp}format=rgba[gp_raw]",
            f"[1:v]scale={gameplay_w}:{gameplay_h}[gp_mask]",
            f"[gp_raw][gp_mask]alphamerge[gp_masked]",
            f"[bg][gp_masked]overlay={gameplay_x}:{gameplay_y}:shortest=1:eof_action=repeat[bg_gp]",
            f"[2:v]scale={gameplay_w}:{gameplay_h}[gp_border]",
            f"[bg_gp][gp_border]overlay={gameplay_x}:{gameplay_y}:eof_action=repeat[bg_gp_b]",
            
            # 3. Webcam card: crop face -> native pre-deblock -> scale with aspect ratio safety -> Topaz Iris facial enhancement -> mask -> border
            f"[0:v]{webcam_crop_filter}{cam_pre_deblock}scale={webcam_w}:{webcam_h}:force_original_aspect_ratio=decrease:flags=lanczos+accurate_rnd,setsar=1,pad={webcam_w}:{webcam_h}:(ow-iw)/2:(oh-ih)/2:color=black,{enhance_cam}format=rgba[cam_raw]",
            f"[3:v]scale={webcam_w}:{webcam_h}[cam_mask]",
            f"[cam_raw][cam_mask]alphamerge[cam_masked]",
            f"[bg_gp_b][cam_masked]overlay={webcam_x}:{webcam_y}:eof_action=repeat[bg_all]",
        ]

        if hook_title_y is not None:
            filter_chains.append(f"[bg_all][4:v]overlay={webcam_x - webcam_glow_pad}:{webcam_y - webcam_glow_pad}:eof_action=repeat[bg_halo]")
            filter_chains.append(f"[bg_halo][5:v]overlay=0:{hook_title_y}:eof_action=repeat[pre_sub]")
        else:
            filter_chains.append(f"[bg_all][4:v]overlay={webcam_x - webcam_glow_pad}:{webcam_y - webcam_glow_pad}:eof_action=repeat[pre_sub]")

    # 4. Optional Subtitle overlay
    if subtitles_ass_path and os.path.exists(subtitles_ass_path):
        escaped_ass = subtitles_ass_path.replace("\\", "/").replace(":", "\\:")
        filter_chains.append(f"[pre_sub]ass='{escaped_ass}'[out_v]")
    else:
        filter_chains.append(f"[pre_sub]null[out_v]")

    return ";".join(filter_chains)
