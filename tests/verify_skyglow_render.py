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
    ensure_studio_font,
)

def verify_studio_flow():
    print("=== Testing Studio Flow Caption Engine & Libass Font Rendering ===")
    assert ensure_studio_font is ensure_skyglow_font, "Expected ensure_studio_font alias"
    font_family, f_dir = ensure_studio_font()
    print(f"  [OK] Font family resolved: {font_family} in {f_dir}")
    assert font_family == "Montserrat ExtraBold", f"Expected Montserrat ExtraBold, got {font_family}"

    main_ttf = os.path.join(f_dir, "Montserrat-ExtraBold.ttf")
    assert os.path.exists(main_ttf) and os.path.getsize(main_ttf) >= 20 * 1024, f"Missing {main_ttf}"
    print(f"  [PASS] Confirmed Montserrat-ExtraBold.ttf ({os.path.getsize(main_ttf)} bytes)")

    os.makedirs("storage/temp", exist_ok=True)
    preview_ass = os.path.abspath("storage/temp/verify_studio_flow_preview.ass")
    motion_ass = os.path.abspath("storage/temp/verify_studio_flow_motion.ass")
    out_png = os.path.abspath("storage/temp/verify_studio_flow.png")
    out_mp4 = os.path.abspath("storage/temp/verify_studio_flow_2sec.mp4")

    # -------------------------------------------------------------
    # 1. Test Static Preview Generation (is_preview=True) + skyglow alias
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
        font_size=62,
        primary_color="#FFFFFF",
        highlight_color="#38BDF8",
        style_preset="skyglow",  # Verify backward-compatible alias routes to studio_flow
        is_preview=True
    )

    with open(preview_ass, "r", encoding="utf-8") as f:
        prev_content = f.read()

    assert "Style: FlowShadow," in prev_content, "Missing FlowShadow style"
    assert "Style: FlowMain," in prev_content, "Missing FlowMain style"
    assert "WrapStyle: 2" in prev_content, "Expected WrapStyle: 2"
    assert ",100,100,-0.5,0," in prev_content, "Expected ScaleX=100, ScaleY=100, Spacing=-0.5"
    assert "\\N" in prev_content, "Expected 2-line balanced wrapping with \\N"
    assert "\\t(" not in prev_content and "\\fad(" not in prev_content, "Preview mode should not contain \\t() or \\fad() tags"
    print("  [PASS] Preview ASS verified: FlowShadow + FlowMain, WrapStyle=2, ScaleX=100, Spacing=-0.5, \\N wrap, alias skyglow->studio_flow")

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
    # 2. Test Motion Generation (is_preview=False) + Profanity Masking
    # -------------------------------------------------------------
    segments_motion = [
        {
            "start": 0.0,
            "end": 0.85,
            "text": "OH MY FUCKING GOSH",
            "words": [
                {"word": "OH", "start": 0.0, "end": 0.2},
                {"word": "MY", "start": 0.2, "end": 0.4},
                {"word": "FUCKING", "start": 0.4, "end": 0.65},
                {"word": "GOSH", "start": 0.65, "end": 0.85}
            ]
        },
        {
            "start": 1.1,
            "end": 1.9,
            "text": "CHAT ARE YOU READY?",
            "words": [
                {"word": "CHAT", "start": 1.1, "end": 1.3},
                {"word": "ARE", "start": 1.3, "end": 1.5},
                {"word": "YOU", "start": 1.5, "end": 1.7},
                {"word": "READY?", "start": 1.7, "end": 1.9}
            ]
        }
    ]

    generate_ass_subtitles(
        segments=segments_motion,
        output_path=motion_ass,
        font_family="Montserrat ExtraBold",
        font_size=62,
        primary_color="#FFFFFF",
        highlight_color="#38BDF8",
        style_preset="studio_flow",
        censor_profanity=True,
        is_preview=False
    )

    with open(motion_ass, "r", encoding="utf-8") as f:
        motion_content = f.read()

    shadow_lines = [ln for ln in motion_content.splitlines() if ln.startswith("Dialogue: 0,") and ",FlowShadow," in ln]
    main_lines = [ln for ln in motion_content.splitlines() if ln.startswith("Dialogue: 1,") and ",FlowMain," in ln]
    assert len(shadow_lines) == 2 and len(main_lines) == 2, f"Expected 1 Dialogue per layer per phrase (got {len(shadow_lines)}, {len(main_lines)})"
    print("  [PASS] Continuous single-event-per-layer structure verified (2 phrases -> 2 FlowShadow + 2 FlowMain)")

    # Verify zero-gap bridging (0.85s -> 1.10s)
    assert "0:00:01.10,FlowMain," in motion_content, "Expected phrase 0 bridged cleanly to 1.10s"
    # Verify 60fps zoom & fad
    assert "\\fad(75,110)\\fscx96\\fscy96\\t(0," in motion_content and "\\fscx104\\fscy104)" in motion_content, "Missing continuous zoom or fad(75,110)"
    # Verify 3-state color transitions (dim #A1A1AA -> &H00AAAA1A1&? BGR: AA A1 A1 -> &H00AAA1A1&, highlight #38BDF8 -> &H00F8BD38&, primary #FFFFFF -> &H00FFFFFF&)
    assert "&H00AAA1A1&" in motion_content and "&H00F8BD38&" in motion_content and "&H00FFFFFF&" in motion_content, "Missing 3-state color transitions (dim -> highlight -> white)"
    # Verify profanity masking
    assert "F*CKING" in motion_content and "FUCKING" not in motion_content, "Expected profanity masking F*CKING"
    print("  [PASS] Zero-gap bridging, continuous 96%->104% zoom, 3-state color transitions, and profanity masking verified")

    # -------------------------------------------------------------
    # 3. Render 2-second test MP4 with FFmpeg + libass
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
    print(f"  [PASS] Rendered 2-second Studio Flow verification clip ({os.path.getsize(out_mp4)} bytes)")
    print("=== ALL STUDIO FLOW VERIFICATIONS PASSED! ===")

if __name__ == "__main__":
    verify_studio_flow()
