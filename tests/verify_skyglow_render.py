import os
import sys
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.subtitle_generator import generate_ass_subtitles, FONTS_DIR, ensure_skyglow_font

def verify_skyglow():
    print("=== Testing SkyGlow Subtitle Generation & Libass Font Rendering ===")
    font_family, f_dir = ensure_skyglow_font()
    print(f"  [OK] Font family resolved: {font_family} in {f_dir}")
    
    os.makedirs("storage/temp", exist_ok=True)
    ass_path = os.path.abspath("storage/temp/verify_skyglow.ass")
    out_png = os.path.abspath("storage/temp/verify_skyglow.png")
    
    text = "THIS IS WRONG WITH TODAY'S SOCIETY"
    words = [
        {"word": "THIS", "start": 0.0, "end": 0.3},
        {"word": "IS", "start": 0.3, "end": 0.6},
        {"word": "WRONG", "start": 0.6, "end": 0.9},
        {"word": "WITH", "start": 0.9, "end": 1.2},
        {"word": "TODAY'S", "start": 1.2, "end": 1.6},
        {"word": "SOCIETY", "start": 1.6, "end": 2.1}
    ]
    
    generate_ass_subtitles(
        segments=[{
            "start": 0.0,
            "end": 2.5,
            "text": text,
            "words": words
        }],
        output_path=ass_path,
        font_family="Poppins Black",
        font_size=60,
        primary_color="#FFFFFF",
        highlight_color="#22FF66",
        style_preset="skyglow",
        is_preview=True
    )
    
    with open(ass_path, "r", encoding="utf-8") as f:
        ass_content = f.read()
    
    assert "Style: SkyOuter" in ass_content, "Missing SkyOuter style"
    assert "Style: SkyInner" in ass_content, "Missing SkyInner style"
    assert "Style: SkyFill" in ass_content, "Missing SkyFill style"
    assert "Dialogue: 0" in ass_content, "Missing Layer 0 event"
    assert "Dialogue: 1" in ass_content, "Missing Layer 1 event"
    assert "Dialogue: 2" in ass_content, "Missing Layer 2 event"
    assert "\\N" in ass_content, "Expected 2-line auto-stacking with \\N"
    print("  [PASS] ASS Content structure verified with 3 layers and \\N split")
    
    escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
    escaped_fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    filter_str = f"color=c=black:s=1080x1920:d=1,ass='{escaped_ass}':fontsdir='{escaped_fonts}'"
    
    cmd = [
        "bin/ffmpeg.exe", "-y",
        "-f", "lavfi", "-i", filter_str,
        "-frames:v", "1",
        out_png
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"FFmpeg failed with code {res.returncode}: {res.stderr}"
    assert os.path.exists(out_png) and os.path.getsize(out_png) > 10000, f"PNG not rendered: {out_png}"
    
    stderr_lower = res.stderr.lower()
    for line in res.stderr.splitlines():
        if "poppins" in line.lower() or "fontselect" in line.lower() or "loading font file" in line.lower():
            print("  ", line)
            
    print(f"  [PASS] Rendered 1-frame verification PNG ({os.path.getsize(out_png)} bytes): {out_png}")
    print("=== ALL SKYGLOW VERIFICATIONS PASSED! ===")

if __name__ == "__main__":
    verify_skyglow()
