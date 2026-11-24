import os
import sys
import time

print("[*] Starting profiling script...", flush=True)

from backend.viral_detector import (
    extract_audio_features,
    detect_viral_moments,
    extract_candidate_motion,
    extract_clip_thumbnail
)

video_path = r"C:\kkkkk\🔴 BEATING GTA 6 RIGHT NOW 100% (FINAL MISSION)_0_3548.mp4"
duration = 3548.1

print(f"[*] Testing video: {video_path} (duration: {duration:.1f}s)", flush=True)

t0 = time.time()
print("[1] Testing extract_audio_features...", flush=True)
features = extract_audio_features(video_path, duration)
t1 = time.time()
print(f"[1] Audio extraction finished in {t1 - t0:.2f}s, frames: {len(features.get('rms', []))}", flush=True)

print("[2] Running detect_viral_moments directly...", flush=True)
t2 = time.time()
clips = detect_viral_moments(
    video_path=video_path,
    video_duration=duration,
    subtitles=None,
    min_duration=10.0,
    max_duration=30.0,
    target_clips=None, # Auto mode
    profile="balanced",
    use_llm=True
)
t3 = time.time()
print(f"[2] detect_viral_moments finished in {t3 - t2:.2f}s! Returned {len(clips)} clips.", flush=True)

for i, c in enumerate(clips):
    print(f"Clip #{c['rank']}: {c['title']} | {c['start']}s -> {c['end']}s ({c['duration']}s) | Score: {c['virality_score']} | Climax: {c['reason']} | Thumb: {c.get('has_thumbnail')}", flush=True)
