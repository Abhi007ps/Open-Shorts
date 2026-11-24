import os
import sys
import json
from backend.clipper import render_clip

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
uploads_dir = os.path.join(BASE_DIR, "storage", "uploads")

video_path = sys.argv[1] if len(sys.argv) > 1 else None
if not video_path:
    candidates = ["test_stream.mp4", "document_6053073585516323938.mp4"]
    for c in candidates:
        p = os.path.join(uploads_dir, c)
        if os.path.isfile(p):
            video_path = p
            break
    if not video_path and os.path.exists(uploads_dir):
        for f in os.listdir(uploads_dir):
            if f.lower().endswith(".mp4"):
                video_path = os.path.join(uploads_dir, f)
                break

if not video_path or not os.path.isfile(video_path):
    print("No sample video found in storage/uploads. Please provide video path: python render_test_enhanced.py <path_to_video>")
    sys.exit(0)

subs_file = os.path.join(BASE_DIR, "storage", "default_subtitles.json")
subs = json.load(open(subs_file, "r", encoding="utf-8")) if os.path.exists(subs_file) else []

template_config = {
    "canvas_w": 1080, "canvas_h": 1920,
    "bg_blur_sigma": 30, "bg_brightness": -0.12,
    "gameplay_w": 960, "gameplay_h": 540, "gameplay_radius": 36,
    "gameplay_border_w": 6, "gameplay_border_color": "#FFFFFF", "gameplay_y": 690,
    "webcam_w": 300, "webcam_h": 300, "webcam_border_w": 6,
    "webcam_border_color": "#FFFFFF", "webcam_y": 540,
    "webcam_crop": {"x": 22, "y": 160, "w": 84, "h": 84},
    "sharpen_amount": 0.8, "contrast_boost": 1.12, "saturation_boost": 1.25,
    "brightness_offset": 0.01
}

subtitle_config = {
    "font_family": "Impact", "font_size": 60, "position_y": 82,
    "style_preset": "hormozi", "primary_color": "#FFFFFF",
    "highlight_color": "#FFDE00", "outline_color": "#000000",
    "outline_width": 5, "shadow_depth": 2, "is_uppercase": True
}

print(f"Rendering enhanced test clip with CAS upscale & synchronized subtitles on: {video_path}")
out_path = os.path.join(BASE_DIR, "storage", "outputs", "test_enhanced_output.mp4")
res = render_clip(
    video_path=video_path,
    start_time=0.0,
    end_time=6.0,
    template_config=template_config,
    subtitle_config=subtitle_config,
    subtitles=subs,
    output_path=out_path
)
print(f"Render complete: {out_path} ({os.path.getsize(out_path) / (1024*1024):.2f} MB)")
