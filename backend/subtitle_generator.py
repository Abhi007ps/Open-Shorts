import os
import re
import math
import urllib.request
from typing import List, Dict, Any, Optional, Tuple

FONTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts"))
os.makedirs(FONTS_DIR, exist_ok=True)

def ensure_skyglow_font() -> Tuple[str, str]:
    """
    Ensures Montserrat-ExtraBold.ttf and Montserrat-ExtraBoldItalic.ttf are downloaded locally to assets/fonts/.
    Returns (font_family_name, fonts_dir).
    """
    font_specs = [
        ("Montserrat-ExtraBold.ttf", "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf"),
        ("Montserrat-ExtraBoldItalic.ttf", "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBoldItalic.ttf"),
    ]
    for fname, url in font_specs:
        target = os.path.join(FONTS_DIR, fname)
        if not os.path.exists(target) or os.path.getsize(target) < 20 * 1024:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OpenShorts/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp, open(target, "wb") as f:
                    f.write(resp.read())
            except Exception as e:
                print(f"[WARN] Could not download {fname}: {e}")

    montserrat_main = os.path.join(FONTS_DIR, "Montserrat-ExtraBold.ttf")
    if os.path.exists(montserrat_main) and os.path.getsize(montserrat_main) >= 20 * 1024:
        return ("Montserrat ExtraBold", FONTS_DIR)

    poppins_fb = os.path.join(FONTS_DIR, "Poppins-Black.ttf")
    if os.path.exists(poppins_fb) and os.path.getsize(poppins_fb) >= 20 * 1024:
        return ("Poppins Black", FONTS_DIR)

    return ("Arial Black", FONTS_DIR)

ensure_studio_font = ensure_skyglow_font

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

def _repl_fuck(m):
    w = m.group(0)
    rest = m.group(1)
    if w.isupper():
        return "F*CK" + rest.upper()
    if w[0].isupper():
        return "F*ck" + rest.lower()
    return "f*ck" + rest.lower()

def _repl_shit(m):
    w = m.group(0)
    rest = m.group(1)
    if w.isupper():
        return "SH*T" + rest.upper()
    if w[0].isupper():
        return "Sh*t" + rest.lower()
    return "sh*t" + rest.lower()

def _repl_bitch(m):
    w = m.group(0)
    rest = m.group(1)
    if w.isupper():
        return "B*TCH" + rest.upper()
    if w[0].isupper():
        return "B*tch" + rest.lower()
    return "b*tch" + rest.lower()

def _repl_asshole(m):
    w = m.group(0)
    rest = m.group(1)
    if w.isupper():
        return "AS*HOLE" + rest.upper()
    if w[0].isupper():
        return "As*hole" + rest.lower()
    return "as*hole" + rest.lower()

def _repl_ass(m):
    w = m.group(0)
    if w.isupper():
        return "AS*"
    if w[0].isupper():
        return "As*"
    return "as*"

def _repl_dick(m):
    w = m.group(0)
    rest = m.group(1)
    if w.isupper():
        return "D*CK" + rest.upper()
    if w[0].isupper():
        return "D*ck" + rest.lower()
    return "d*ck" + rest.lower()

def _repl_pussy(m):
    w = m.group(0)
    suf = m.group(1)
    if suf.lower() == 'ies':
        return "P*SSIES" if w.isupper() else "p*ssies"
    return "P*SSY" if w.isupper() else ("P*ssy" if w[0].isupper() else "p*ssy")

def mask_profanity(text: str) -> str:
    """
    Masks explicit profanity with asterisks while preserving word boundaries and casing.
    fuck* -> F*CK*, shit* -> SH*T*, bitch* -> B*TCH*, asshole* -> AS*HOLE*, ass -> AS*,
    dick* -> D*CK*, pussy/pussies -> P*SSY/P*SSIES.
    """
    if not text:
        return text
    s = re.sub(r'\b[fF][uU][cC][kK](\w*)\b', _repl_fuck, text)
    s = re.sub(r'\b[sS][hH][iI][tT](\w*)\b', _repl_shit, s)
    s = re.sub(r'\b[bB][iI][tT][cC][hH](\w*)\b', _repl_bitch, s)
    s = re.sub(r'\b[aA][sS][sS][hH][oO][lL][eE](\w*)\b', _repl_asshole, s)
    s = re.sub(r'\b[aA][sS][sS]\b', _repl_ass, s)
    s = re.sub(r'\b[dD][iI][cC][kK](\w*)\b', _repl_dick, s)
    s = re.sub(r'\b[pP][uU][sS][sS](y|ies)\b', _repl_pussy, s, flags=re.IGNORECASE)
    return s

def _is_font_installed(font_name: str) -> bool:
    if os.name == "nt":
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        if os.path.isdir(fonts_dir):
            clean = font_name.lower().replace(" ", "").replace("-", "")
            try:
                for f in os.listdir(fonts_dir):
                    if clean in f.lower().replace(" ", "").replace("-", ""):
                        return True
            except Exception:
                pass
    return False

def resolve_font_family(font_family: str, style_preset: str = "") -> str:
    """Resolves font family with fallbacks for cross-platform portability."""
    if style_preset in ("studio_flow", "skyglow"):
        if not font_family or font_family in ("Montserrat ExtraBold", "Poppins Black", "Arial Black", ""):
            return ensure_skyglow_font()[0]
        return font_family
    return font_family or "Arial Black"

SKYGLOW_THEMES = {
    "green": {
        "fill": "&H0014FF7D&",
        "edge": "&H0014FF7D&",
        "edge_w": 0.5,
        "shadow": "&H000A5314&",
        "glow": "&H0014FF50&",
        "italic": 0,
        "size_mult": 1.0,
        "shadow_d": 6,
    },
    "cyan": {
        "fill": "&H00F2F0A8&",
        "edge": "&H00FFFFEF&",
        "edge_w": 1.5,
        "shadow": "&H0040230C&",
        "glow": "&H00E8D92B&",
        "italic": 0,
        "size_mult": 1.0,
        "shadow_d": 6,
    },
    "peak": {
        "fill": "&H0050FF1E&",
        "edge": "&H0050FF1E&",
        "edge_w": 0.5,
        "shadow": "&H00063A06&",
        "glow": "&H0014FF50&",
        "italic": -1,
        "size_mult": 1.35,
        "shadow_d": 9,
    },
}

_SKYGLOW_GREEN_TRIGGERS = (
    "OH MY", "GOSH", "GOD", "NO WAY", "WHAT THE", "LET'S GO", "BACKFLIP",
    "CRAZY", "INSANE", "WAIT", "LOOK AT", "BRO", "HOLY", "KILL", "DEAD",
    "STOP", "HAHA", "LMAO", "SH*T", "F*CK", "AS*"
)
_SKYGLOW_PEAK_TRIGGERS = ("BOOM", "DAMN", "SH*T", "F*CK", "CLUTCH", "GOAT")

def _classify_skyglow_theme(text: str, words: list, seg_idx: int, prev_theme: str, consec_cyan: int = 0) -> str:
    """Classifies each phrase into 'peak', 'green', or 'cyan' based on energy and rhythm."""
    u = str(text or "").upper().strip()
    if len(words) <= 2 and len(u) <= 16:
        if "!" in u or re.search(r'([A-Z])\1{2,}', u) or any(kw in u for kw in _SKYGLOW_PEAK_TRIGGERS):
            return "peak"

    if any(tr in u for tr in _SKYGLOW_GREEN_TRIGGERS):
        return "green"
    if u.endswith(("!", "?")) and prev_theme != "green":
        return "green"

    if consec_cyan >= 2:
        return "green"
    return "cyan"

def _wrap_skyglow(tokens: List[str], max_chars: int = 20) -> List[str]:
    """Wraps progressive tokens into up to 2 centered lines without upper-line reflow."""
    if not tokens:
        return []
    lines = []
    cur = tokens[0]
    for tok in tokens[1:]:
        if len(lines) == 0 and len(cur) + 1 + len(tok) > max_chars:
            lines.append(cur)
            cur = tok
        else:
            cur += " " + tok
    lines.append(cur)
    return lines[:2]

def _grow(tau: float) -> float:
    """Exponential ease-out growth curve measured from reference video."""
    return 1.0 + 0.08 * (1.0 - math.exp(-max(tau, 0.0) / 0.6))

def generate_ass_subtitles(
    segments: List[Dict[str, Any]],
    output_path: str,
    font_family: str = "Arial Black",
    font_size: int = 56,
    primary_color: str = "#FFFFFF",
    highlight_color: str = "#00FF66",
    outline_color: str = "#000000",
    outline_width: int = 2,
    shadow_depth: int = 2,
    position_x: float = 50.0, # percentage from left (0 = left, 50 = center, 100 = right)
    position_y: float = 50.0, # percentage from top (0 = top, 50 = middle, 100 = bottom)
    style_preset: str = "skyglow", # skyglow, speed, box, clean, hormozi, mrbeast, neon, fire
    is_uppercase: bool = True,
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    hook_config: Optional[Dict[str, Any]] = None,
    sync_offset_ms: int = 0,
    censor_profanity: bool = True,
    is_preview: bool = False
) -> str:
    r"""
    Generates a complete ASS subtitle file with free 2D positioning (\pos), word highlights,
    optional auto-profanity masking, and progressive word reveals.
    Features the reference SkyGlow preset: 3 synchronized ASS layers (SkyOuter wide neon bloom,
    SkyInner tight halo, SkyFill crisp text with subtle drop shadow), locked-position per-word
    smooth fade-in with zero horizontal shifting, smooth phrase fade-out, 2-line auto-stacking,
    and Green/Cyan/Gold neon palette cycling.
    """
    effective_preset = "studio_flow" if style_preset in ("studio_flow", "skyglow") else style_preset
    effective_font = resolve_font_family(font_family, effective_preset)
    sync_offset = float(sync_offset_ms or 0) / 1000.0
    # Calculate exact pixel position on canvas
    pos_x = int(play_res_x * (float(position_x) / 100.0))
    pos_y = int(play_res_y * (float(position_y) / 100.0))
    pos_tag = f"{{\\an5\\pos({pos_x},{pos_y})}}"
    
    # Border style: 1 = outline + drop shadow, 3 = opaque / translucent box
    border_style = 3 if effective_preset == "box" else 1
    
    ass_primary = hex_to_ass_color(primary_color)
    ass_highlight = hex_to_ass_color(highlight_color)
    ass_outline = hex_to_ass_color(outline_color)
    ass_back = hex_to_ass_color("#000000", alpha=140 if border_style == 3 else 80)

    bold = -1 # True in ASS
    italic = 0 # Upright

    if effective_preset == "studio_flow":
        styles_section = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: FlowShadow,{effective_font},{font_size},&HFF000000&,&H00000000&,&H58000000&,&H00000000&,-1,0,0,0,100,100,-0.5,0,1,6,0,5,60,60,60,1
Style: FlowMain,{effective_font},{font_size},{ass_primary},{ass_highlight},&H25000000&,&H65000000&,-1,0,0,0,100,100,-0.5,0,1,1.6,2,5,60,60,60,1"""
    else:
        styles_section = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{effective_font},{font_size},{ass_primary},{ass_highlight},{ass_outline},{ass_back},{bold},{italic},0,0,100,100,1,0,{border_style},{outline_width},{shadow_depth},5,60,60,60,1"""

    wrap_style = 2 if effective_preset == "studio_flow" else 0
    header = f"""[Script Info]
Title: OpenShorts Custom Template Subtitles
ScriptType: v4.00+
WrapStyle: {wrap_style}
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {play_res_x}
PlayResY: {play_res_y}

{styles_section}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
    lines = [header]

    valid_segs = []
    for seg in segments:
        s_t = max(0.0, float(seg.get("start", 0)) + sync_offset)
        e_t = max(s_t + 0.05, float(seg.get("end", 0)) + sync_offset)
        raw_text = re.sub(r'[,.]+', '', str(seg.get("text", ""))).strip()
        if censor_profanity and raw_text:
            raw_text = mask_profanity(raw_text)
        if raw_text and e_t > s_t:
            valid_segs.append({
                "start": s_t,
                "end": e_t,
                "text": raw_text.upper() if is_uppercase else raw_text,
                "words": seg.get("words", [])
            })
    valid_segs.sort(key=lambda s: s["start"])

    # Zero-gap phrase bridging for studio_flow (or standard non-overlap clamp for others)
    if effective_preset == "studio_flow" and not is_preview:
        for k in range(len(valid_segs)):
            if k + 1 < len(valid_segs):
                next_start = valid_segs[k + 1]["start"]
                gap = next_start - valid_segs[k]["end"]
                if 0.0 <= gap <= 0.40:
                    valid_segs[k]["end"] = next_start
                elif gap > 0.40:
                    valid_segs[k]["end"] = min(valid_segs[k]["end"] + 0.14, next_start - 0.01)
                else:
                    valid_segs[k]["end"] = max(valid_segs[k]["start"] + 0.04, next_start)
            else:
                valid_segs[k]["end"] += 0.14
            valid_segs[k]["end"] = max(valid_segs[k]["start"] + 0.05, valid_segs[k]["end"])
    else:
        for k in range(len(valid_segs) - 1):
            if valid_segs[k]["end"] > valid_segs[k + 1]["start"]:
                valid_segs[k]["end"] = max(valid_segs[k]["start"] + 0.04, valid_segs[k + 1]["start"])

    ass_dim = hex_to_ass_color("#A1A1AA")

    for seg_idx, seg in enumerate(valid_segs):
        start_t = seg["start"]
        end_t = seg["end"]
        text = seg["text"]
        words = seg.get("words", [])
        start_str = format_ass_timestamp(start_t)
        end_str = format_ass_timestamp(end_t)

        cleaned_words = []
        if words:
            for w in words:
                w_txt = re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()
                if censor_profanity and w_txt:
                    w_txt = mask_profanity(w_txt)
                if w_txt:
                    w_s = float(w.get("start", start_t)) + sync_offset
                    w_e = float(w.get("end", end_t)) + sync_offset
                    cleaned_words.append({
                        "word": w_txt.upper() if is_uppercase else w_txt,
                        "start": max(start_t, min(end_t, w_s)),
                        "end": max(start_t, min(end_t, w_e))
                    })
        if not cleaned_words and text:
            raw_w_list = text.split()
            dur = max(0.1, end_t - start_t)
            cleaned_words = [
                {
                    "word": w.upper() if is_uppercase else w,
                    "start": start_t + (i / max(1, len(raw_w_list))) * dur,
                    "end": start_t + ((i + 1) / max(1, len(raw_w_list))) * dur
                }
                for i, w in enumerate(raw_w_list)
            ]

        # ==========================================
        # PRESET A: Studio Flow Native-Libass Engine
        # ==========================================
        if effective_preset == "studio_flow":
            num_w = len(cleaned_words)
            if num_w == 0:
                continue

            # Auto-wrap longer phrases into 2 balanced centered lines
            split_idx = None
            if num_w >= 4 and len(text) > 18:
                best_k = max(1, min(num_w - 1, num_w // 2))
                min_diff = 9999
                for k in range(1, num_w):
                    l1 = " ".join(w["word"] for w in cleaned_words[:k])
                    l2 = " ".join(w["word"] for w in cleaned_words[k:])
                    diff = abs(len(l1) - len(l2))
                    if diff < min_diff:
                        min_diff = diff
                        best_k = k
                split_idx = best_k

            def _join_flow(w_items):
                out_s = ""
                for idx_w, w_it in enumerate(w_items):
                    out_s += w_it
                    if idx_w < len(w_items) - 1:
                        out_s += "\\N" if (split_idx is not None and idx_w == split_idx - 1) else " "
                return out_s

            plain_wrapped = _join_flow([w["word"] for w in cleaned_words])

            if is_preview:
                mid_idx = num_w // 2 if num_w > 1 else 0
                prev_words = []
                for j, cw in enumerate(cleaned_words):
                    if j < mid_idx:
                        prev_words.append(f"{{\\1c{ass_primary}}}{cw['word']}")
                    elif j == mid_idx:
                        prev_words.append(f"{{\\1c{ass_highlight}}}{cw['word']}")
                    else:
                        prev_words.append(f"{{\\1c{ass_dim}}}{cw['word']}")
                main_body = _join_flow(prev_words)
                lines.append(
                    f"Dialogue: 0,{start_str},{end_str},FlowShadow,,0,0,0,,{{\\an5\\pos({pos_x},{pos_y})\\blur9}}{plain_wrapped}"
                )
                lines.append(
                    f"Dialogue: 1,{start_str},{end_str},FlowMain,,0,0,0,,{{\\an5\\pos({pos_x},{pos_y})\\blur0.3}}{main_body}"
                )
            else:
                w_starts = [start_t]
                for i in range(1, num_w):
                    w_s = cleaned_words[i].get("start", start_t)
                    s_i = max(w_s, w_starts[i - 1] + 0.04)
                    s_i = min(s_i, end_t - 0.04 * (num_w - i))
                    w_starts.append(s_i)

                total_ms = max(180, int(round((end_t - start_t) * 1000)))
                anim = f"\\an5\\pos({pos_x},{pos_y})\\fad(75,110)\\fscx96\\fscy96\\t(0,{total_ms},\\fscx104\\fscy104)"

                main_words = []
                for j in range(num_w):
                    w_str = cleaned_words[j]["word"]
                    rel_s = max(0, int(round((w_starts[j] - start_t) * 1000)))
                    rel_e = int(round((w_starts[j + 1] - start_t) * 1000)) if (j + 1 < num_w) else total_ms

                    if j == 0:
                        if num_w > 1:
                            w_tag = f"{{\\1c{ass_highlight}\\t({rel_e},{rel_e + 70},\\1c{ass_primary})}}{w_str}"
                        else:
                            w_tag = f"{{\\1c{ass_highlight}}}{w_str}"
                    elif 0 < j < num_w - 1:
                        w_tag = f"{{\\1c{ass_dim}\\t({rel_s},{rel_s + 50},\\1c{ass_highlight})\\t({rel_e},{rel_e + 70},\\1c{ass_primary})}}{w_str}"
                    else:
                        w_tag = f"{{\\1c{ass_dim}\\t({rel_s},{rel_s + 50},\\1c{ass_highlight})}}{w_str}"
                    main_words.append(w_tag)

                main_body = _join_flow(main_words)
                lines.append(
                    f"Dialogue: 0,{start_str},{end_str},FlowShadow,,0,0,0,,{{{anim}\\blur9}}{plain_wrapped}"
                )
                lines.append(
                    f"Dialogue: 1,{start_str},{end_str},FlowMain,,0,0,0,,{{{anim}}}{main_body}"
                )

        # ==========================================
        # PRESET B: Speed / Clean / Box / Other Styles
        # ==========================================
        else:
            neon_glow = r"{\blur4}" if effective_preset == "neon" else ""
            # 1. Multi-word segment with active karaoke word highlighting
            if len(cleaned_words) > 1 and effective_preset in ("speed", "hormozi", "mrbeast", "neon", "box", "fire"):
                num_w = len(cleaned_words)
                w_starts = [start_t]
                for i in range(1, num_w):
                    s_i = max(cleaned_words[i]["start"], w_starts[i - 1] + 0.04)
                    s_i = min(s_i, end_t - 0.04 * (num_w - i))
                    w_starts.append(s_i)

                for i in range(num_w):
                    disp_start = w_starts[i]
                    disp_end = w_starts[i + 1] if (i + 1 < num_w) else end_t
                    disp_end = max(disp_start + 0.04, disp_end)
                    w_start_str = format_ass_timestamp(disp_start)
                    w_end_str = format_ass_timestamp(disp_end)

                    entrance_tag = r"{\fscx106\fscy106\t(0,80,\fscx100\fscy100)}" if (i == 0 and style_preset != "speed") else ""

                    formatted_words = []
                    for j, word_item in enumerate(cleaned_words):
                        if j == i:
                            formatted_words.append(f"{{\\c{ass_highlight}}}{word_item['word']}{{\\c{ass_primary}}}")
                        else:
                            formatted_words.append(word_item['word'])
                    
                    line_text = " ".join(formatted_words)
                    lines.append(f"Dialogue: 0,{w_start_str},{w_end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{entrance_tag}{{\\c{ass_primary}}}{line_text}")

            # 2. Single word at a time mode
            elif len(cleaned_words) == 1:
                raw_w = cleaned_words[0]["word"]
                pop_tag = "" if style_preset in ("speed", "clean") else r"{\fscx114\fscy114\t(0,90,\fscx100\fscy100)}"
                highlight = ass_primary if style_preset == "clean" else ass_highlight
                lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{pop_tag}{{\\c{highlight}}}{raw_w}")

            # 3. Simple text line
            else:
                lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{pos_tag}{neon_glow}{{\\c{ass_primary}}}{text}")
            
    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return output_path

def generate_srt_subtitles(segments: List[Dict[str, Any]], output_path: str, is_uppercase: bool = False, censor_profanity: bool = True) -> str:
    """Generates standard SRT subtitles file without full stops or commas, with optional profanity masking."""
    lines = []
    idx = 1
    for seg in segments:
        start_t = float(seg.get("start", 0))
        end_t = float(seg.get("end", 0))
        text = re.sub(r'[,.]+', '', seg.get("text", "")).strip()
        if censor_profanity and text:
            text = mask_profanity(text)
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
