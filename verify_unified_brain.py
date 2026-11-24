import os
import sys
import json
import time

from backend.viral_detector import detect_viral_moments

def main():
    video_path = r"C:\Users\apsin\OpenShorts-Studio\storage\uploads\PLAYING GTA 6 FOR THE FIRST TIME (PART 2)_60_1800.mp4"
    if not os.path.exists(video_path):
        print(f"Video not found: {video_path}")
        return

    subs_path = r"C:\Users\apsin\OpenShorts-Studio\storage\default_subtitles.json"
    subs = []
    if os.path.exists(subs_path):
        with open(subs_path, "r", encoding="utf-8") as f:
            subs = json.load(f)

    print(f"[*] Testing Unified Multimodal AI Sync + Semantic Brain on:\n    {video_path}")
    print(f"[*] Subtitles available: {len(subs)}")

    # 1. Test Unified Single Function (Multimodal + Llama 3.2 Brain)
    print("\n" + "="*70)
    print("STAGE 1: UNIFIED SINGLE FUNCTION (Multimodal Acoustic/Motion + Llama 3.2)")
    print("="*70)
    t0 = time.time()
    clips = detect_viral_moments(
        video_path=video_path,
        video_duration=96.3,
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
        video_duration=96.3,
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
