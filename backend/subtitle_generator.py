import re
from typing import List, Dict, Any, Optional

def hex_to_ass_color(hex_str: str, alpha: int = 0) -> str:
    """
    Converts a hex color string like '#FFDE00' or 'FFDE00' to ASS format '&HAABBGGRR&'.
    ASS uses BGR ordering instead of RGB.
    alpha: 0 (opaque) to 255 (fully transparent).
    """
    clean_hex = hex_str.strip().lstrip('#')
    if len(clean_hex) == 3:
        clean_hex = ''.join([c*2 for c in clean_hex])
    if len(clean_hex) != 6:
        clean_hex = 'FFFFFF'
    
    r = clean_hex[0:2]
    g = clean_hex[2:4]
    b = clean_hex[4:6]
    a = f"{alpha:02X}"
    return f"&H{a}{b}{g}{r}&"

def format_ass_timestamp(seconds: float) -> str:
    """Formats seconds as H:MM:SS.cs for ASS format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{cs:02d}"

def format_srt_timestamp(seconds: float) -> str:
    """Formats seconds as HH:MM:SS,mmm for SRT format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

def generate_ass_subtitles(
    segments: List[Dict[str, Any]],
    output_path: str,
    font_family: str = "Impact",
    font_size: int = 56,
    primary_color: str = "#FFFFFF",
    highlight_color: str = "#FFDE00",
    outline_color: str = "#000000",
    outline_width: int = 4,
    shadow_depth: int = 2,
    position_x: float = 50.0, # percentage from left (0 = left, 50 = center, 100 = right)
    position_y: float = 82.0, # percentage from top (0 = top, 50 = middle, 100 = bottom)
    style_preset: str = "speed", # speed, hormozi, mrbeast, neon, box, fire, clean
    is_uppercase: bool = True,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    hook_config: Optional[Dict[str, Any]] = None,
    sync_offset_ms: int = 0
) -> str:
    r"""
    Generates a complete ASS subtitle file with free 2D positioning (\pos), word highlights,
    and optional top viral hook headline banner.
    Supports 1-word-at-a-time, multi-word chunking, and multiple aesthetic style templates.
    """
    sync_offset = float(sync_offset_ms or 0) / 1000.0
    # Calculate exact pixel position on canvas
    pos_x = int(play_res_x * (float(position_x) / 100.0))
    pos_y = int(play_res_y * (float(position_y) / 100.0))
    pos_tag = f"{{\\an5\\pos({pos_x},{pos_y})}}"
    
    # Border style: 1 = outline + drop shadow, 3 = opaque / translucent box
    border_style = 3 if style_preset == "box" else 1
    
    ass_primary = hex_to_ass_color(primary_color)
    ass_highlight = hex_to_ass_color(highlight_color)
    ass_outline = hex_to_ass_color(outline_color)
    ass_back = hex_to_ass_color("#000000", alpha=140 if border_style == 3 else 80)

    bold = -1 # True in ASS
    italic = 0

    header = f"""[Script Info]
Title: OpenShorts Custom Template Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},{font_size},{ass_primary},{ass_highlight},{ass_outline},{ass_back},{bold},{italic},0,0,100,100,1,0,{border_style},{outline_width},{shadow_depth},5,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
    lines = [header]

    for seg in segments:
        start_t = max(0.0, float(seg.get("start", 0)) + sync_offset)
        end_t = max(start_t + 0.1, float(seg.get("end", 0)) + sync_offset)
        text = re.sub(r'[,.]+', '', seg.get("text", "")).strip()
        if not text or end_t <= start_t:
            continue
        
        if is_uppercase:
            text = text.upper()
        
        words = seg.get("words", [])
        start_str = format_ass_timestamp(start_t)
        end_str = format_ass_timestamp(end_t)
        neon_glow = r"{\blur4}" if style_preset == "neon" else ""
        
        # 1. Multi-word segment with active karaoke word highlighting
        if words and len(words) > 1 and style_preset in ("speed", "hormozi", "mrbeast", "neon", "box", "fire"):
            total_w = len(words)
            if style_preset == "speed":
                # Smooth Reference Style (IShowSpeed / C:\ppp): Zero bounce, rock-solid anchor, crisp color highlight
                for i, w in enumerate(words):
                    w_start = float(w.get("start", start_t)) + sync_offset
                    w_end = float(w.get("end", end_t)) + sync_offset
                    w_start = max(start_t, min(end_t - 0.05, w_start))
                    w_end = max(w_start + 0.08, min(end_t, w_end))
                    w_start_str = format_ass_timestamp(w_start)
                    w_end_str = format_ass_timestamp(w_end)
                    formatted_words = []
                    for j, word_item in enumerate(words):
                        raw_w = re.sub(r'[,.]+', '', word_item.get("word", "")).strip()
                        if is_uppercase:
                            raw_w = raw_w.upper()
                        if j == i:
                            formatted_words.append(f"{{\\c{ass_highlight}}}{raw_w}{{\\c{ass_primary}}}")
                        else:
                            formatted_words.append(f"{{\\c{ass_primary}}}{raw_w}")
                    lines.append(f"Dialogue: 0,{w_start_str},{w_end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{' '.join(formatted_words)}")
            else:
                for i, w in enumerate(words):
                    # Precise word boundaries: highlight strictly when spoken, release when word ends
                    w_start = float(w.get("start", start_t)) + sync_offset
                    w_end = float(w.get("end", end_t)) + sync_offset
                    
                    # Clamp within segment boundaries
                    w_start = max(start_t, min(end_t - 0.05, w_start))
                    w_end = max(w_start + 0.10, min(end_t, w_end))
                    w_dur = w_end - w_start
                    
                    # Active Word Pop Bounce Animation (Hormozi / MrBeast style)
                    if w_dur >= 0.16:
                        pop_dur = min(0.11, w_dur * 0.36)
                        t_pop_end = w_start + pop_dur
                        w_pop_start_str = format_ass_timestamp(w_start)
                        w_pop_end_str = format_ass_timestamp(t_pop_end)
                        w_settle_end_str = format_ass_timestamp(w_end)
                        
                        # Pop Phase: active word popped 118%
                        words_pop = []
                        for j, word_item in enumerate(words):
                            raw_w = re.sub(r'[,.]+', '', word_item.get("word", "")).strip()
                            if is_uppercase:
                                raw_w = raw_w.upper()
                            if j == i:
                                words_pop.append(f"{{\\fscx118\\fscy118\\c{ass_highlight}}}{raw_w}{{\\fscx100\\fscy100\\c{ass_primary}}}")
                            else:
                                words_pop.append(f"{{\\fscx100\\fscy100\\c{ass_primary}}}{raw_w}")
                        lines.append(f"Dialogue: 0,{w_pop_start_str},{w_pop_end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{' '.join(words_pop)}")
                        
                        # Settle Phase: active word settles to 104%
                        words_settle = []
                        for j, word_item in enumerate(words):
                            raw_w = re.sub(r'[,.]+', '', word_item.get("word", "")).strip()
                            if is_uppercase:
                                raw_w = raw_w.upper()
                            if j == i:
                                words_settle.append(f"{{\\fscx104\\fscy104\\c{ass_highlight}}}{raw_w}{{\\fscx100\\fscy100\\c{ass_primary}}}")
                            else:
                                words_settle.append(f"{{\\fscx100\\fscy100\\c{ass_primary}}}{raw_w}")
                        lines.append(f"Dialogue: 0,{w_pop_end_str},{w_settle_end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{' '.join(words_settle)}")
                    else:
                        # Short word (< 160ms): single punchy pop at 115%
                        w_start_str = format_ass_timestamp(w_start)
                        w_end_str = format_ass_timestamp(w_end)
                        formatted_words = []
                        for j, word_item in enumerate(words):
                            raw_w = re.sub(r'[,.]+', '', word_item.get("word", "")).strip()
                            if is_uppercase:
                                raw_w = raw_w.upper()
                            if j == i:
                                formatted_words.append(f"{{\\fscx115\\fscy115\\c{ass_highlight}}}{raw_w}{{\\fscx100\\fscy100\\c{ass_primary}}}")
                            else:
                                formatted_words.append(f"{{\\fscx100\\fscy100\\c{ass_primary}}}{raw_w}")
                        lines.append(f"Dialogue: 0,{w_start_str},{w_end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{' '.join(formatted_words)}")

        # 2. Single word at a time mode (high-energy punchy highlight with pop bounce)
        elif words and len(words) == 1:
            raw_w = re.sub(r'[,.]+', '', words[0].get("word", text)).strip()
            if is_uppercase:
                raw_w = raw_w.upper()
            w_dur = end_t - start_t
            if w_dur >= 0.16:
                pop_dur = min(0.12, w_dur * 0.38)
                t_pop_end = start_t + pop_dur
                lines.append(f"Dialogue: 0,{format_ass_timestamp(start_t)},{format_ass_timestamp(t_pop_end)},Default,,0,0,0,,{pos_tag}{neon_glow}{{\\fscx122\\fscy122\\c{ass_highlight}}}{raw_w}")
                lines.append(f"Dialogue: 0,{format_ass_timestamp(t_pop_end)},{format_ass_timestamp(end_t)},Default,,0,0,0,,{pos_tag}{neon_glow}{{\\fscx100\\fscy100\\c{ass_highlight}}}{raw_w}")
            else:
                lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{{\\fscx116\\fscy116\\c{ass_highlight}}}{raw_w}")

        # 3. Simple text line with custom primary color and optional glow
        else:
            lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{{\\c{ass_primary}}}{text}")
            
    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return output_path

def generate_srt_subtitles(segments: List[Dict[str, Any]], output_path: str, is_uppercase: bool = False) -> str:
    """Generates standard SRT subtitles file without full stops or commas."""
    lines = []
    idx = 1
    for seg in segments:
        start_t = float(seg.get("start", 0))
        end_t = float(seg.get("end", 0))
        text = re.sub(r'[,.]+', '', seg.get("text", "")).strip()
        if not text or end_t <= start_t:
            continue
        if is_uppercase:
            text = text.upper()
        
        lines.append(str(idx))
        lines.append(f"{format_srt_timestamp(start_t)} --> {format_srt_timestamp(end_t)}")
        lines.append(text)
        lines.append("")
        idx += 1
        
    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path
