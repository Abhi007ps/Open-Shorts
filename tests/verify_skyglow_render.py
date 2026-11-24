import os
import sys
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.subtitle_generator import (
    generate_ass_subtitles,
    FONTS_DIR,
    ensure_skyglow_font,
    _classify_skyglow_theme,
)
from backend.template_engine import generate_template_assets, build_composite_filtergraph

def verify_skyglow():
    print("=== Testing Measured SkyGlow Subtitle Engine, Seam Shadow & Climax Facecam Punch ===")
    font_family, f_dir = ensure_skyglow_font()
    print(f"  [OK] Font family resolved: {font_family} in {f_dir}")
    assert font_family == "Montserrat ExtraBold", f"Expected Montserrat ExtraBold, got {font_family}"

    main_ttf = os.path.join(f_dir, "Montserrat-ExtraBold.ttf")
    italic_ttf = os.path.join(f_dir, "Montserrat-ExtraBoldItalic.ttf")
    assert os.path.exists(main_ttf) and os.path.getsize(main_ttf) >= 20 * 1024, f"Missing {main_ttf}"
    assert os.path.exists(italic_ttf) and os.path.getsize(italic_ttf) >= 20 * 1024, f"Missing {italic_ttf}"
    print(f"  [PASS] Confirmed Montserrat-ExtraBold.ttf ({os.path.getsize(main_ttf)} bytes) & Montserrat-ExtraBoldItalic.ttf ({os.path.getsize(italic_ttf)} bytes)")

    # 1. Verify Auto-Classifier Themes
    t1 = _classify_skyglow_theme("OH MY GOSH", [{"word": "OH"}, {"word": "MY"}, {"word": "GOSH"}], 0, "")
    assert t1 == "green", f"Expected 'green' for OH MY GOSH, got {t1}"
    t2 = _classify_skyglow_theme("CHAT YOU Y'ALL READY?", [{"word": "CHAT"}, {"word": "YOU"}, {"word": "Y'ALL"}, {"word": "READY?"}], 1, t1)
    assert t2 == "cyan", f"Expected 'cyan' for CHAT YOU Y'ALL READY? after green, got {t2}"
    t3 = _classify_skyglow_theme("SIUUUU!!!", [{"word": "SIUUUU!!!"}], 2, t2)
    assert t3 == "peak", f"Expected 'peak' for SIUUUU!!!, got {t3}"
    print("  [PASS] Auto-theme classifier verified: green ('OH MY GOSH'), cyan ('CHAT YOU Y'ALL READY?'), peak ('SIUUUU!!!')")

    os.makedirs("storage/temp", exist_ok=True)
    preview_ass = os.path.abspath("storage/temp/verify_skyglow_preview.ass")
    motion_ass = os.path.abspath("storage/temp/verify_skyglow_motion.ass")
    out_png = os.path.abspath("storage/temp/verify_skyglow.png")
    out_mp4 = os.path.abspath("storage/temp/verify_skyglow_2sec.mp4")
    out_climax_mp4 = os.path.abspath("storage/temp/verify_skyglow_climax_1sec.mp4")

    # -------------------------------------------------------------
    # 2. Test Static Preview Generation (is_preview=True)
    # -------------------------------------------------------------
    text1 = "THIS IS WRONG WITH TODAY'S SOCIETY"
    words1 = [
        {"word": "THIS", "start": 0.0, "end": 0.3},
        {"word": "IS", "start": 0.3, "end": 0.6},
        {"word": "WRONG", "start": 0.6, "end": 0.9},
        {"word": "WITH", "start": 0.9, "end": 1.2},
        {"word": "TODAY'S", "start": 1.2, "end": 1.6},
        {"word": "SOCIETY", "start": 1.6, "end": 2.1},
    ]

    generate_ass_subtitles(
        segments=[{
            "start": 0.0,
            "end": 2.5,
            "text": text1,
            "words": words1
        }],
        output_path=preview_ass,
        font_family="Montserrat ExtraBold",
        font_size=74,
        primary_color="#A8F0F2",
        highlight_color="#7DFF14",
        style_preset="skyglow",
        is_preview=True
    )

    with open(preview_ass, "r", encoding="utf-8") as f:
        prev_content = f.read()

    for sname in ("Sky_green", "Sky_green_glow", "Sky_cyan", "Sky_cyan_glow", "Sky_peak", "Sky_peak_glow"):
        assert f"Style: {sname}," in prev_content, f"Missing style {sname}"
    assert "WrapStyle: 2" in prev_content, "Expected WrapStyle: 2"
    assert ",118,100,3,0," in prev_content, "Expected ScaleX=118, ScaleY=100, Spacing=3"
    assert "\\t(" not in prev_content, "Preview mode should not contain \\t() animation tags"
    print("  [PASS] Preview ASS verified: 6 Sky_* styles, ScaleX=118, Spacing=3, WrapStyle=2, static preview")

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
    # 3. Test Motion Generation & Both Bug Fixes (is_preview=False)
    # -------------------------------------------------------------
    segments_motion = [
        {
            "start": 0.0,
            "end": 0.7,
            "text": "OH MY GOSH",
            "words": [
                {"word": "OH", "start": 0.0, "end": 0.2},
                {"word": "MY", "start": 0.2, "end": 0.4},
                {"word": "GOSH", "start": 0.4, "end": 0.7}
            ]
        },
        {
            "start": 0.9,
            "end": 1.4,
            "text": "CHAT YOU Y'ALL READY?",
            "words": [
                {"word": "CHAT", "start": 0.9, "end": 1.05},
                {"word": "YOU", "start": 1.05, "end": 1.2},
                {"word": "Y'ALL", "start": 1.2, "end": 1.3},
                {"word": "READY?", "start": 1.3, "end": 1.4}
            ]
        },
        {
            "start": 1.5,
            "end": 2.0,
            "text": "SIUUUU!!!",
            "words": [
                {"word": "SIUUUU!!!", "start": 1.5, "end": 2.0}
            ]
        }
    ]

    generate_ass_subtitles(
        segments=segments_motion,
        output_path=motion_ass,
        font_family="Montserrat ExtraBold",
        font_size=74,
        primary_color="#A8F0F2",
        highlight_color="#7DFF14",
        style_preset="skyglow",
        is_preview=False
    )

    with open(motion_ass, "r", encoding="utf-8") as f:
        motion_content = f.read()

    # Check Bug Fix #1: Layer 0 _glow fades newest word with \alpha&HFF& -> \alpha&H88&
    glow_lines = [ln for ln in motion_content.splitlines() if ln.startswith("Dialogue: 0,") and "_glow," in ln]
    assert glow_lines and any("\\alpha&HFF&" in ln and "\\alpha&H88&" in ln for ln in glow_lines), "Missing synchronized glow fade \\alpha&HFF& -> \\alpha&H88& on Layer 0"
    print("  [PASS] Bug Fix #1 verified: Layer 0 _glow fades newest word (\\alpha&HFF& -> \\alpha&H88&)")

    # Check Bug Fix #2: Newest word chains \t(pop_ms,dur_ms,...) so it keeps growing with the line
    assert any("\\t(90," in ln for ln in glow_lines) and any("\\t(90," in ln for ln in motion_content.splitlines() if "Dialogue: 1," in ln), "Missing tail_continue \\t(90,dur_ms,...) continuous growth on newest word"
    print("  [PASS] Bug Fix #2 verified: Newest word chains \\t(pop_ms,dur_ms,...) for seamless growth")

    # Check phrase handoff clamping (seg 0 ends 0.7 + 0.35 clamped to <= 0.90 next start)
    assert "0:00:00.90,Sky_green" in motion_content, "Expected phrase 0 clamped neatly at 0.90s before phrase 1"
    assert ",Sky_green," in motion_content and ",Sky_cyan," in motion_content and ",Sky_peak," in motion_content, "Missing classified themes in motion events"
    print("  [PASS] Theme assignment & non-overlapping phrase handoffs verified")

    # -------------------------------------------------------------
    # 4. Render 2-second test MP4 with FFmpeg + libass
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

    found_montserrat = False
    for line in res_mp4.stderr.splitlines():
        if "montserrat" in line.lower() or "fontselect" in line.lower() or "loading font file" in line.lower():
            print("  ", line)
            if "montserrat" in line.lower():
                found_montserrat = True
    assert found_montserrat, "Libass did not log loading Montserrat font!"
    print(f"  [PASS] Rendered 2-second verification clip ({os.path.getsize(out_mp4)} bytes) with Montserrat font loaded")

    # -------------------------------------------------------------
    # 5. Render 1-second test with split-screen seam shadow + climax_zoom_enabled=True
    # -------------------------------------------------------------
    assets = generate_template_assets(layout_mode="split_screen", prefix="verify_seam_")
    fg_climax = build_composite_filtergraph(
        canvas_w=1080, canvas_h=1920,
        layout_mode="split_screen",
        climax_zoom_enabled=True,
        climax_rel_time=0.4,
        input_video_w=1280, input_video_h=720,
        pixel_generator=False,
        sharpen_amount=0.0,
        micro_texture=0.0,
        dynamic_range_pop=False,
        deblock_level="none",
        subtitles_ass_path=motion_ass
    )
    assert "color=black@0.28:t=fill" in fg_climax, "Missing subtle split-screen seam drop shadow"
    cmd_climax = [
        "bin/ffmpeg.exe", "-y",
        "-f", "lavfi", "-i", "color=c=navy:s=1280x720:d=1:r=30",
        "-i", assets["gameplay_mask"],
        "-i", assets["gameplay_border"],
        "-i", assets["webcam_mask"],
        "-i", assets["webcam_border"],
        "-filter_complex", fg_climax,
        "-map", "[out_v]",
        "-t", "1",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        out_climax_mp4
    ]
    res_climax = subprocess.run(cmd_climax, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res_climax.returncode == 0, f"FFmpeg climax split-screen failed: {res_climax.stderr[-1000:]}"
    assert os.path.exists(out_climax_mp4) and os.path.getsize(out_climax_mp4) > 10000
    print(f"  [PASS] Rendered 1-second split-screen + seam shadow + climax_zoom_enabled=True clip ({os.path.getsize(out_climax_mp4)} bytes)")
    print("=== ALL SKYGLOW MEASURED REFERENCE VERIFICATIONS PASSED! ===")

if __name__ == "__main__":
    verify_skyglow()
