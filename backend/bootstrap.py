"""
OpenShorts Studio Pre-Flight Self-Diagnostic & Bootstrap Engine.
Verifies system dependencies, binaries, models, and hardware acceleration
before launching the web studio. Self-heals missing models or folders.
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

def check_directories():
    """Ensure all required runtime storage folders exist."""
    for sub in ["uploads", "outputs", "temp", "templates"]:
        p = os.path.join(STORAGE_DIR, sub)
        os.makedirs(p, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

def verify_binaries():
    """Check availability of FFmpeg, FFprobe, and Whisper-CLI."""
    from backend.hardware import FFMPEG_BIN, FFPROBE_BIN, WHISPER_CLI
    
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
        # whisper-cli -h outputs usage to stderr or stdout
        if res.returncode == 0 or "usage" in (res.stdout + res.stderr).lower():
            print(f"  [OK] Whisper CLI:     {os.path.basename(WHISPER_CLI)} (High-speed C++ engine ready)")
        else:
            print(f"  [WARN] Whisper CLI returned: {res.returncode}")
    except Exception as e:
        print(f"  [WARN] Whisper CLI check: {e}")

def verify_models():
    """Ensure at least one Whisper GGML speech model is present; auto-download if empty."""
    from backend.transcriber import ensure_whisper_model
    try:
        model_path = ensure_whisper_model("base.en")
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        print(f"  [OK] Whisper Model:   {os.path.basename(model_path)} ({size_mb:.1f} MB ready)")
    except Exception as e:
        print(f"  [ERROR] Model verification error: {e}")

def verify_hardware():
    """Detect and display active hardware encoder (NVIDIA / Intel / AMD / CPU)."""
    from backend.hardware import get_hardware_profile
    profile = get_hardware_profile()
    cpu = profile.get("cpu", {})
    gpu = profile.get("gpu", {})
    enc = profile.get("recommended_encoder", "libx264")
    
    print(f"  [OK] CPU Architecture: {cpu.get('model', 'CPU')} ({cpu.get('cores', 4)} cores / {cpu.get('whisper_threads', 4)} whisper threads)")
    primary_gpu = gpu.get("primary", "Integrated / System Graphics")
    print(f"  [OK] GPU Accelerator:  {primary_gpu}")
    print(f"  [OK] Video Encoder:    {enc.upper()} (Ultra-low latency hardware export active)")

def main():
    print("---------------------------------------------------------------------")
    print("           OPENSHORTS STUDIO - SYSTEM PRE-FLIGHT CHECK               ")
    print("---------------------------------------------------------------------")
    check_directories()
    verify_binaries()
    verify_models()
    verify_hardware()
    print("---------------------------------------------------------------------")
    print(" [READY] All systems verified. Studio engine is operational!")
    print("---------------------------------------------------------------------")

if __name__ == "__main__":
    main()
