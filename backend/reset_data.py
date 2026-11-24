"""
OpenShorts Studio - Factory Reset & Clean Slate Utility
Cleans out all previous clips, uploaded streams, exports, temporary cache,
and session states so the application starts 100% brand new for any new user.
CRITICALLY PRESERVES:
- Bundled binaries (bin/ffmpeg.exe, bin/Release/whisper-cli.exe, SIMD DLLs)
- Downloaded speech models (models/ggml-base.en.bin, etc.)
- Demo footage (assets/demo/ or storage/uploads/demo.mp4)
- Core source code (backend/, frontend/)
"""

import os
import sys
import shutil

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
TEMP_DIR = os.path.join(STORAGE_DIR, "temp")
UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")
OUTPUTS_DIR = os.path.join(STORAGE_DIR, "outputs")
TEMPLATES_DIR = os.path.join(STORAGE_DIR, "templates")
THUMBNAILS_DIR = os.path.join(STORAGE_DIR, "thumbnails")

def clean_directory(dir_path: str, preserve_demo: bool = False):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        return

    count = 0
    for fname in os.listdir(dir_path):
        if fname in (".gitkeep", "README.md"):
            continue
        # Preserve demo sample video if present in uploads
        if preserve_demo and "demo" in fname.lower() and fname.endswith(".mp4"):
            continue

        fpath = os.path.join(dir_path, fname)
        try:
            if os.path.isfile(fpath) or os.path.islink(fpath):
                os.remove(fpath)
                count += 1
            elif os.path.isdir(fpath):
                shutil.rmtree(fpath, ignore_errors=True)
                count += 1
        except Exception as e:
            print(f"  [WARN] Could not remove {fname}: {e}")

    print(f"  [CLEANED] {os.path.basename(dir_path)}/ (removed {count} items)")

def clean_pycache():
    count = 0
    for root, dirs, files in os.walk(BASE_DIR):
        for d in dirs:
            if d == "__pycache__":
                p = os.path.join(root, d)
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    count += 1
                except Exception:
                    pass
    print(f"  [CLEANED] Removed {count} __pycache__ folders")

def reset_to_clean_slate():
    print("=====================================================================")
    print("      OPENSHORTS STUDIO - FACTORY RESET & CLEAN SLATE ENGINE        ")
    print("=====================================================================")
    print("\n[*] Clearing previous user session data...")

    # 1. Clean storage directories
    clean_directory(OUTPUTS_DIR)
    clean_directory(TEMP_DIR)
    clean_directory(THUMBNAILS_DIR)
    clean_directory(TEMPLATES_DIR)
    clean_directory(UPLOADS_DIR, preserve_demo=True)

    # 2. Clean pycache
    clean_pycache()

    # 3. Verify preserved essentials
    bin_ffmpeg = os.path.join(BASE_DIR, "bin", "ffmpeg.exe")
    models_dir = os.path.join(BASE_DIR, "models")
    
    print("\n[*] Verifying preserved essentials:")
    if os.path.exists(bin_ffmpeg):
        print("  [OK] FFmpeg hardware engine intact.")
    else:
        print("  [INFO] System FFmpeg will be discovered dynamically.")
        
    if os.path.exists(models_dir) and any(f.endswith(".bin") for f in os.listdir(models_dir)):
        print("  [OK] Whisper AI speech models intact.")

    print("\n=====================================================================")
    print(" [DONE] OpenShorts Studio is now 100% clean and ready for a new user!")
    print("        When launched, it will start completely fresh with zero")
    print("        previous clips, outputs, or session history.")
    print("=====================================================================")

if __name__ == "__main__":
    reset_to_clean_slate()
