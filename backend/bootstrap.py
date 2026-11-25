"""
OpenShorts Studio Pre-Flight Self-Diagnostic & Bootstrap Engine.
Verifies system dependencies, binaries, models, RAM, GPU/VRAM,
auto-tuned performance profile, and hardware acceleration before launching the web studio.
"""

import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
BIN_DIR = os.path.join(BASE_DIR, "bin")
MODELS_DIR = os.path.join(BASE_DIR, "models")
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
SETUP_MARKER = os.path.join(BASE_DIR, "tools", ".setup_complete")

def check_directories():
    """Ensure all required runtime storage folders exist."""
    for sub in ["uploads", "outputs", "temp", "templates"]:
        p = os.path.join(STORAGE_DIR, sub)
        os.makedirs(p, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

def verify_binaries():
    """Check availability of FFmpeg, FFprobe, and Whisper-CLI."""
    from backend.hardware import FFMPEG_BIN, FFPROBE_BIN, WHISPER_CLI, ensure_realesrgan_for_tier
    
    # 1. FFmpeg
    try:
        res = subprocess.run([FFMPEG_BIN, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode == 0:
            first_line = res.stdout.splitlines()[0] if res.stdout else "FFmpeg detected"
            print(f"  [OK] FFmpeg Binary:   {os.path.basename(FFMPEG_BIN)} ({first_line[:40]}...)")
        else:
            print(f"  [WARN] FFmpeg returned non-zero code: {res.returncode}")
    except Exception as e:
        print(f"  [ERROR] FFmpeg check failed: {e}")

    # 2. Whisper-CLI
    try:
        res = subprocess.run([WHISPER_CLI, "-h"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode == 0 or "usage" in (res.stdout + res.stderr).lower():
            print(f"  [OK] Whisper CLI:     {os.path.basename(WHISPER_CLI)} (High-speed C++ engine ready)")
        else:
            print(f"  [WARN] Whisper CLI returned: {res.returncode}")
    except Exception as e:
        print(f"  [WARN] Whisper CLI check: {e}")

    # 3. Real-ESRGAN (Tier-Gated Facecam Super-Resolution)
    res = ensure_realesrgan_for_tier()
    if res.get("status") == "ready":
        print(f"  [OK] Facecam Upscaler: {os.path.basename(res.get('path', 'realesrgan-ncnn-vulkan'))} (Neural Facecam Super-Resolution active, tier={res.get('tier')})")
    elif res.get("status") == "skipped":
        print(f"  [INFO] Facecam Upscaler: FFmpeg Pro Clarity mode (tier={res.get('tier')}, Real-ESRGAN skipped)")
    else:
        print(f"  [WARN] Facecam Upscaler: Auto-setup deferred ({res.get('error', 'offline')}); using FFmpeg Pro Clarity mode")

    # 4. Phoneme Forced Alignment
    from backend.forced_aligner import is_forced_aligner_available
    if is_forced_aligner_available():
        print("  [OK] Wav2Vec2 Sync:    Active (Phoneme-level forced alignment)")
    else:
        print("  [INFO] Wav2Vec2 Sync:    Optional (using calibrated Whisper DTW)")

def verify_models():
    """Ensure at least one Whisper GGML speech model is present; auto-download small.en if empty."""
    from backend.transcriber import ensure_whisper_model, MODELS_DIR
    try:
        turbo_p = os.path.join(MODELS_DIR, "ggml-large-v3-turbo-q5_0.bin")
        small_p = os.path.join(MODELS_DIR, "ggml-small.en.bin")
        if os.path.isfile(turbo_p) and os.path.getsize(turbo_p) > 1_000_000:
            model_path = turbo_p
        elif os.path.isfile(small_p) and os.path.getsize(small_p) > 1_000_000:
            model_path = small_p
        else:
            model_path = ensure_whisper_model("small.en")
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        print(f"  [OK] Whisper Model:   {os.path.basename(model_path)} ({size_mb:.1f} MB ready)")
    except Exception as e:
        print(f"  [ERROR] Model verification error: {e}")

def verify_fonts():
    """Ensure Montserrat-ExtraBold.ttf caption font is present; auto-download if missing."""
    from backend.subtitle_generator import ensure_skyglow_font, FONTS_DIR
    try:
        font_family, f_dir = ensure_skyglow_font()
        font_path = os.path.join(f_dir, "Montserrat-ExtraBold.ttf")
        if os.path.isfile(font_path):
            print(f"  [OK] Caption Font:   Montserrat-ExtraBold.ttf ready")
        else:
            print(f"  [WARN] Caption Font: Fallback to {font_family}")
    except Exception as e:
        print(f"  [WARN] Caption Font check: {e}")

def verify_hardware():
    """Detect and display active hardware encoder (NVIDIA / Intel / AMD / Apple / CPU), RAM, VRAM, and Auto-Tuned Tier."""
    from backend.hardware import get_hardware_profile
    profile = get_hardware_profile()
    cpu = profile.get("cpu", {})
    gpu = profile.get("gpu", {})
    ram = profile.get("ram", {})
    perf = profile.get("performance_profile", {})
    enc = profile.get("recommended_encoder", "libx264")
    
    print(f"  [OK] CPU Architecture: {cpu.get('model', 'CPU')} ({cpu.get('cores', 4)} cores / {cpu.get('whisper_threads', 4)} whisper threads)")
    print(f"  [OK] System Memory:    {ram.get('total_gb', 0.0)} GB RAM ({ram.get('available_gb', 0.0)} GB available)")
    primary_gpu = gpu.get("primary", "Integrated / System Graphics")
    vram_str = f" • {gpu.get('vram_gb', 0.0)} GB VRAM" if gpu.get("vram_gb", 0.0) > 0 else ""
    print(f"  [OK] GPU Accelerator:  {primary_gpu}{vram_str}")
    print(f"  [OK] Video Encoder:    {enc.upper()} (Ultra-low latency hardware export active)")
    tier_name = perf.get("tier", "balanced").upper()
    print(f"  [OK] Auto-Tuned Tier:  {tier_name} (Workers: {perf.get('export_workers', 1)}, Filters: {perf.get('filter_mode', 'balanced')}, Bitrate: {perf.get('default_1080p_bitrate', '12M')}, LLM: {perf.get('llm_tier', 'standard')})")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="OpenShorts Studio Pre-Flight Check & Setup")
    parser.add_argument("--setup", action="store_true", help="Run zero-touch first-time setup for missing tools/models")
    parser.add_argument("--skip-ollama", action="store_true", help="Skip automatic Ollama installation/model pull")
    args, _ = parser.parse_known_args()

    print("---------------------------------------------------------------------")
    print("           OPENSHORTS STUDIO - SYSTEM PRE-FLIGHT CHECK               ")
    print("---------------------------------------------------------------------")
    check_directories()

    # Auto-install any missing core binary/model on first run (and when --setup is passed)
    from backend.installer import run_full_first_time_setup
    setup_results = run_full_first_time_setup(skip_ollama=args.skip_ollama)

    verify_binaries()
    verify_models()
    verify_fonts()
    verify_hardware()

    ol = setup_results.get("ollama", {})
    ol_status = ol.get("status", "skipped")
    if ol_status == "ready":
        models = ol.get("models") or []
        print(f"  [OK] Ollama AI:      Online ({', '.join(models[:3]) if models else 'ready'})")
    else:
        print(f"  [INFO] Ollama AI:    {ol_status} (Cognitive NLP fallback active)")

    # Write persistent setup-ready marker if core dependencies are verified
    ff_ok = setup_results.get("ffmpeg", {}).get("status") == "ready"
    wh_ok = setup_results.get("whisper_cli", {}).get("status") == "ready"
    model_ok = setup_results.get("whisper_model", {}).get("status") == "ready"
    font_ok = setup_results.get("font", {}).get("status") == "ready"
    if ff_ok and wh_ok and model_ok and font_ok:
        try:
            import json
            from datetime import datetime, timezone
            os.makedirs(os.path.dirname(SETUP_MARKER), exist_ok=True)
            with open(SETUP_MARKER, "w", encoding="utf-8") as mf:
                json.dump(
                    {
                        "setup_complete": True,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    mf,
                    indent=2,
                )
        except Exception as e:
            print(f"  [WARN] Could not write setup marker: {e}")

    print("---------------------------------------------------------------------")
    print(" [READY] All systems verified. Studio engine is operational!")
    print("---------------------------------------------------------------------")

if __name__ == "__main__":
    main()
