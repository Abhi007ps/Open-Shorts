import os
import sys
import json
from backend.viral_detector import detect_viral_moments

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
uploads_dir = os.path.join(BASE_DIR, "storage", "uploads")

video_path = sys.argv[1] if len(sys.argv) > 1 else None
if not video_path:
    # Look for sample in storage/uploads
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
    print("No sample video found in storage/uploads. Please provide video path: python test_viral.py <path_to_video>")
    sys.exit(0)

subs_file = os.path.join(BASE_DIR, "storage", "default_subtitles.json")
subs = json.load(open(subs_file, "r", encoding="utf-8")) if os.path.exists(subs_file) else []

print(f"Testing viral detection on: {video_path}")
print("=== 1. AUTO MODE (Engine selects natural number of high virality clips) ===")
clips_auto = detect_viral_moments(video_path, 96.3, subs, min_duration=8.0, max_duration=25.0, target_clips=None)
print(f"Engine identified {len(clips_auto)} viral clips:")
for c in clips_auto:
    print(f"  * [Virality: {c['virality_score']}/100 | {c['reason']}] {c['title']} ({c['start']}s -> {c['end']}s, {c['duration']}s)")

print("\n=== 2. MANUAL MODE (User requested exactly 6 clips, min 10s, max 20s) ===")
clips_manual = detect_viral_moments(video_path, 96.3, subs, min_duration=10.0, max_duration=20.0, target_clips=6)
print(f"Engine selected top 6 viral clips:")
for c in clips_manual:
    print(f"  * [Virality: {c['virality_score']}/100 | {c['reason']}] {c['title']} ({c['start']}s -> {c['end']}s, {c['duration']}s)")
