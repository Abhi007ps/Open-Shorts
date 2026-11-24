import os
import sys
import json
import time
from backend.clipper import render_clip, auto_generate_clips

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
uploads_dir = os.path.join(BASE_DIR, "storage", "uploads")

VIDEO_PATH = sys.argv[1] if len(sys.argv) > 1 else None
if not VIDEO_PATH:
    candidates = ["test_stream.mp4", "document_6053073585516323938.mp4"]
    for c in candidates:
        p = os.path.join(uploads_dir, c)
        if os.path.isfile(p):
            VIDEO_PATH = p
            break
    if not VIDEO_PATH and os.path.exists(uploads_dir):
        for f in os.listdir(uploads_dir):
            if f.lower().endswith(".mp4"):
                VIDEO_PATH = os.path.join(uploads_dir, f)
                break

if not VIDEO_PATH or not os.path.isfile(VIDEO_PATH):
    print("No sample video found in storage/uploads. Please provide video path: python render_10_clips.py <path_to_video>")
    sys.exit(0)

SUBS_FILE = os.path.join(BASE_DIR, "storage", "default_subtitles.json")
with open(SUBS_FILE, "r", encoding="utf-8") as f:
    all_subtitles = json.load(f)

template_config = {
    "canvas_w": 1080,
    "canvas_h": 1920,
    "bg_blur_sigma": 30,
    "bg_brightness": -0.12,
    "gameplay_w": 960,
    "gameplay_h": 540,
    "gameplay_radius": 36,
    "gameplay_border_w": 6,
    "gameplay_border_color": "#FFFFFF",
    "gameplay_y": 690,
    "webcam_w": 300,
    "webcam_h": 300,
    "webcam_border_w": 6,
    "webcam_border_color": "#FFFFFF",
    "webcam_y": 540,
    "webcam_crop": {"x": 22, "y": 160, "w": 84, "h": 84},
    "sharpen_amount": 0.8,
    "contrast_boost": 1.08,
    "saturation_boost": 1.22,
    "brightness_offset": 0.01
}

subtitle_config = {
    "font_family": "Impact",
    "font_size": 56,
    "position_y": 82,
    "style_preset": "hormozi",
    "primary_color": "#FFFFFF",
    "highlight_color": "#FFDE00",
    "outline_color": "#000000",
    "outline_width": 4,
    "shadow_depth": 2,
    "is_uppercase": True
}

clips = auto_generate_clips(96.3, max_clips=10)
print(f"Starting batch render of {len(clips)} viral clips on {VIDEO_PATH}...")
start_all = time.time()
for idx, clip in enumerate(clips, 1):
    c_start = clip["start"]
    c_end = clip["end"]
    clip_subs = [s for s in all_subtitles if s["start"] < c_end and s["end"] > c_start]
    out_name = f"clip_{idx}_{clip['title'].replace(' ', '_')[:24]}.mp4"
    out_path = os.path.join(BASE_DIR, "storage", "outputs", out_name)
    print(f"[{idx}/{len(clips)}] Rendering '{clip['title']}' ({c_start}s - {c_end}s)...")
    t0 = time.time()
    render_clip(
        video_path=VIDEO_PATH,
        start_time=c_start,
        end_time=c_end,
        template_config=template_config,
        subtitle_config=subtitle_config,
        subtitles=clip_subs,
        output_path=out_path
    )
    print(f"Done in {time.time() - t0:.1f}s -> {out_name}")

print(f"All {len(clips)} clips exported successfully in {time.time() - start_all:.1f}s!")
