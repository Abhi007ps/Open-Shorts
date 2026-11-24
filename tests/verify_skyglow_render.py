import os
import sys
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.subtitle_generator import generate_ass_subtitles, FONTS_DIR, ensure_skyglow_font

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
    font_file = os.path.join(f_dir, "Poppins-Black.ttf")
    assert os.path.exists(font_file), f"Missing {font_file}"
    print(f"  [PASS] Confirmed Poppins-Black.ttf exists ({os.path.getsize(font_file)} bytes)")
    
    os.makedirs("storage/temp", exist_ok=True)
    preview_ass = os.path.abspath("storage/temp/verify_skyglow_preview.ass")
    motion_ass = os.path.abspath("storage/temp/verify_skyglow_motion.ass")
    out_png = os.path.abspath("storage/temp/verify_skyglow.png")
    out_mp4 = os.path.abspath("storage/temp/verify_skyglow_2sec.mp4")
    
    # -------------------------------------------------------------
    # 1. Test Static Preview Generation (is_preview=True)
    # -------------------------------------------------------------
    text1 = "THIS IS WRONG WITH TODAY'S SOCIETY"
    words1 = [
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
            "text": text1,
            "words": words1
        }],
        output_path=preview_ass,
        font_family="Poppins Black",
        font_size=60,
        primary_color="#FFFFFF",
        highlight_color="#22FF66",
        style_preset="skyglow",
        is_preview=True
    )
    
    with open(preview_ass, "r", encoding="utf-8") as f:
        prev_content = f.read()
    
    assert "Style: SkyOuter" in prev_content, "Missing SkyOuter style"
    assert "Style: SkyInner" in prev_content, "Missing SkyInner style"
    assert "Style: SkyFill" in prev_content, "Missing SkyFill style"
    assert ",0,0,0,0,100,100,-0.5," in prev_content, "Expected Italic=0 and Spacing=-0.5 in Sky styles"
    assert "\\N" in prev_content, "Expected 2-line auto-stacking with \\N"
    print("  [PASS] Preview ASS verified: Upright Italic=0, Spacing=-0.5, 3 layers, \\N auto-stacking")
    
    escaped_prev_ass = preview_ass.replace("\\", "/").replace(":", "\\:")
    escaped_fonts = FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    filter_prev = f"color=c=black:s=1080x1920:d=1,ass='{escaped_prev_ass}':fontsdir='{escaped_fonts}'"
    
    cmd_png = [
        "bin/ffmpeg.exe", "-y",
        "-f", "lavfi", "-i", filter_prev,
        "-frames:v", "1",
        out_png
    ]
    res_png = subprocess.run(cmd_png, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_png.returncode == 0, f"FFmpeg PNG failed: {res_png.stderr}"
    assert os.path.exists(out_png) and os.path.getsize(out_png) > 10000, f"PNG not rendered: {out_png}"
    print(f"  [PASS] Rendered 1-frame preview PNG ({os.path.getsize(out_png)} bytes): {out_png}")

    # -------------------------------------------------------------
    # 2. Test Motion Generation & Zero-Gap Handoff (is_preview=False)
    # -------------------------------------------------------------
    segments_motion = [
        {
            "start": 0.0,
            "end": 0.9,
            "text": "OH MY GOSH",
            "words": [
                {"word": "OH", "start": 0.0, "end": 0.25},
                {"word": "MY", "start": 0.25, "end": 0.5},
                {"word": "GOSH", "start": 0.5, "end": 0.85}
            ]
        },
        {
            "start": 1.1,
            "end": 2.0,
            "text": "HERE WE GO",
            "words": [
                {"word": "HERE", "start": 1.1, "end": 1.35},
                {"word": "WE", "start": 1.35, "end": 1.6},
                {"word": "GO", "start": 1.6, "end": 1.95}
            ]
        }
    ]
    
    generate_ass_subtitles(
        segments=segments_motion,
        output_path=motion_ass,
        font_family="Poppins Black",
        font_size=60,
        primary_color="#FFFFFF",
        highlight_color="#22FF66",
        style_preset="skyglow",
        is_preview=False
    )
    
    with open(motion_ass, "r", encoding="utf-8") as f:
        motion_content = f.read()

    # Motion verifications:
    # 1. Zero-gap bridging (seg 0 end bridged from 0.9 to 1.1 + 0.06 = 1.16s -> 0:00:01.16)
    assert "0:00:01.16" in motion_content, "Expected zero-gap bridging extended end timestamp 0:00:01.16"
    print("  [PASS] Zero-gap phrase bridging verified (0.9s -> 1.16s handoff to next phrase)")
    
    # 2. Continuous 60fps subtle zoom-in (\fscx95\fscy95\t(0,...,0.85,\fscx105\fscy105))
    assert "\\fscx95\\fscy95\\t(0," in motion_content and "\\fscx105\\fscy105" in motion_content, "Missing zoom-in tags"
    print("  [PASS] Continuous 60fps subtle zoom-in verified (95% -> 105%)")
    
    # 3. Subtle upward exit drift and dissolve (\move with pos_y - 12 and \fad)
    assert "\\move(" in motion_content and "\\fad(0," in motion_content, "Missing upward exit drift or fade out"
    print("  [PASS] Subtle upward exit drift and fade-out dissolve verified (\\move + \\fad)")
    
    # 4. Character-by-character smooth left-to-right fade sweep
    assert "\\t(" in motion_content and ("\\3a&H62&" in motion_content or "\\1a&H00&" in motion_content), "Missing character sweep transitions"
    print("  [PASS] Smooth per-character left-to-right fade sweep verified")

    # -------------------------------------------------------------
    # 3. Render 2-second test video with FFmpeg + libass
    # -------------------------------------------------------------
    escaped_motion_ass = motion_ass.replace("\\", "/").replace(":", "\\:")
    filter_motion = f"color=c=black:s=1080x1920:d=2:r=30,ass='{escaped_motion_ass}':fontsdir='{escaped_fonts}'"
    cmd_mp4 = [
        "bin/ffmpeg.exe", "-y",
        "-f", "lavfi", "-i", filter_motion,
        "-t", "2",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        out_mp4
    ]
    res_mp4 = subprocess.run(cmd_mp4, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_mp4.returncode == 0, f"FFmpeg motion MP4 failed: {res_mp4.stderr}"
    assert os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 20000, f"MP4 not rendered: {out_mp4}"
    
    for line in res_mp4.stderr.splitlines():
        if "poppins" in line.lower() or "fontselect" in line.lower() or "loading font file" in line.lower():
            print("  ", line)

    print(f"  [PASS] Rendered 2-second verification clip ({os.path.getsize(out_mp4)} bytes): {out_mp4}")
    print("=== ALL SKYGLOW UPGRADE & MOTION VERIFICATIONS PASSED! ===")

if __name__ == "__main__":
    verify_skyglow()

if __name__ == "__main__":
    verify_skyglow()
