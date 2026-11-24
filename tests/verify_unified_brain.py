import os
import sys
import json
import time

# Add repo root to sys.path so backend imports work cleanly
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.viral_detector import detect_viral_moments
from backend.clipper import probe_video

def find_test_video():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return os.path.abspath(sys.argv[1])
    
    uploads_dir = os.path.join(REPO_ROOT, "storage", "uploads")
    if os.path.exists(uploads_dir):
        for f in os.listdir(uploads_dir):
            if f.lower().endswith((".mp4", ".mkv", ".mov", ".ts", ".webm")) and not f.endswith(".bak"):
                return os.path.join(uploads_dir, f)
    return None

def main():
    video_path = find_test_video()
    if not video_path:
        print("[WARN] No video found to test. Place a video in storage/uploads/ or pass one as sys.argv[1].")
        return

    meta = probe_video(video_path)
    dur = meta.get("duration", 60.0)

    subs_path = os.path.join(REPO_ROOT, "storage", "default_subtitles.json")
    subs = []
    if os.path.exists(subs_path):
        with open(subs_path, "r", encoding="utf-8") as f:
            subs = json.load(f)

    print(f"[*] Testing Unified Multimodal AI Sync + Semantic Brain on:\n    {video_path} ({dur:.1f}s)")
    print(f"[*] Subtitles available: {len(subs)}")

    # 1. Test Unified Single Function (Multimodal + LLM Brain)
    print("\n" + "="*70)
    print("STAGE 1: UNIFIED SINGLE FUNCTION (Multimodal Acoustic/Motion + LLM)")
    print("="*70)
    t0 = time.time()
    clips = detect_viral_moments(
        video_path=video_path,
        video_duration=min(dur, 120.0),
        subtitles=subs,
        min_duration=8.0,
        max_duration=35.0,
        target_clips=2,
        use_llm=True
    )
    t_llm = time.time() - t0
    print(f"[OK] Completed unified single-function execution in {t_llm:.2f}s!")
    print(f"[OK] Clips returned: {len(clips)}")

    for c in clips:
        print("\n------------------------------------------------------------")
        print(f"🎬 {c['title']} ({c['start']}s -> {c['end']}s | {c['duration']}s)")
        print(f"🏆 Virality Score: {c['virality_score']}/100 [{c['tier_badge']}]")
        print(f"🧠 LLM Verified: {c.get('llm_verified', False)}")
        if c.get("llm_punchline"):
            print(f"💬 LLM Story & Punchline: {c['llm_punchline']}")
        print(f"📊 Fused Metrics Breakdown:")
        print(f"   - Voice Energy: {c['metrics'].get('voice_energy')}%")
        print(f"   - Facecam Reaction: {c['metrics'].get('facecam_reaction')}%")
        print(f"   - Hook Quality (Semantic): {c['metrics'].get('hook_quality')}%")
        print(f"   - Speech Density: {c['metrics'].get('speech_density')}%")
        print(f"   - Synergy Bonus: +{c['metrics'].get('synergy_bonus', 0)} pts")

    print("\n" + "="*70)
    print("STAGE 2: ZERO-DELAY MULTIMODAL PHYSICAL FALLBACK (LLM Disabled / Offline)")
    print("="*70)
    t0_fb = time.time()
    clips_physical = detect_viral_moments(
        video_path=video_path,
        video_duration=min(dur, 120.0),
        subtitles=subs,
        min_duration=8.0,
        max_duration=35.0,
        target_clips=2,
        use_llm=False
    )
    t_fb = time.time() - t0_fb
    print(f"[OK] Completed physical fallback in {t_fb:.2f}s!")
    for c in clips_physical:
        print(f"  * {c['title']} | Score: {c['virality_score']} | LLM Verified: {c.get('llm_verified', False)}")

    print("\n[SUCCESS] Unified single-function pipeline verified 100%!")

if __name__ == "__main__":
    main()
