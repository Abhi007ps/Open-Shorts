"""
OpenShorts Studio Zero-Touch First-Time Dependency Installer.
Provides idempotent, fail-safe, Zip-Slip-protected installers for:
- FFmpeg & FFprobe (Windows auto-download, macOS/Linux PATH check + hints)
- whisper-cli (Windows CUDA / CPU auto-selection + VC++ Redistributable fallback)
- Tier-gated Real-ESRGAN (via backend.hardware.ensure_realesrgan_for_tier)
- Hardware-matched Whisper GGML model & Studio Flow font
- Ollama daemon & hardware-matched Qwen3 model
"""

import os
import sys
import platform
import shutil
import subprocess
import zipfile
import json
import urllib.request
import stat
import time
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

BIN_DIR = os.path.join(BASE_DIR, "bin")
RELEASE_BIN_DIR = os.path.join(BIN_DIR, "Release")
TEMP_DIR = os.path.join(BASE_DIR, "storage", "temp")
MODELS_DIR = os.path.join(BASE_DIR, "models")

FFMPEG_WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
WHISPER_RELEASES_API = "https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest"
OLLAMA_WIN_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"


def _safe_extract_zip(zip_path: str, dest_dir: str) -> None:
    """Extracts zip_path into dest_dir with Zip-Slip path traversal validation."""
    target_root = Path(dest_dir).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            dest = (target_root / member.filename).resolve()
            if dest != target_root and target_root not in dest.parents:
                raise ValueError(f"Unsafe zip path detected: {member.filename}")
            if member.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)


def _download_file(url: str, dest_path: str, label: str) -> str:
    """
    Downloads url to dest_path atomically via a .part file with User-Agent
    and compact 25%/50%/75%/100% progress updates.
    """
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    part_path = f"{dest_path}.part"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 OpenShorts/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            next_mark = 25
            chunk_size = 262144
            with open(part_path, "wb") as out_f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int((downloaded * 100) / total)
                        while next_mark <= 100 and pct >= next_mark:
                            print(f"  [DL] {label}: {next_mark}%")
                            next_mark += 25
            if total <= 0:
                print(f"  [DL] {label}: 100%")
        os.replace(part_path, dest_path)
        return dest_path
    finally:
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass


def _binary_runs(bin_path: str, arg: str = "-version") -> bool:
    """Verifies a binary exists or resolves on PATH and runs cleanly."""
    if not bin_path:
        return False
    try:
        res = subprocess.run(
            [bin_path, arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if arg == "-h":
            return res.returncode == 0 or "usage" in (res.stdout + res.stderr).lower()
        return res.returncode == 0
    except Exception:
        return False


def ensure_ffmpeg() -> Dict[str, Any]:
    """
    Ensures ffmpeg and ffprobe are available and executable.
    Auto-downloads gyan.dev essentials build into bin/ on Windows if missing.
    """
    import backend.hardware as hw

    ffmpeg_bin = hw.find_binary("ffmpeg")
    ffprobe_bin = hw.find_binary("ffprobe")
    if _binary_runs(ffmpeg_bin, "-version") and _binary_runs(ffprobe_bin, "-version"):
        hw.FFMPEG_BIN = ffmpeg_bin
        hw.FFPROBE_BIN = ffprobe_bin
        return {"status": "ready", "ffmpeg": ffmpeg_bin, "ffprobe": ffprobe_bin}

    system = platform.system()
    if system != "Windows":
        hint = "brew install ffmpeg" if system == "Darwin" else "sudo apt install ffmpeg"
        print(f"  [WARN] FFmpeg/FFprobe not found on PATH. Install with: {hint}")
        return {"status": "missing", "hint": hint}

    os.makedirs(BIN_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    tmp_zip = os.path.join(TEMP_DIR, "ffmpeg-release-essentials.zip")
    tmp_extract = os.path.join(TEMP_DIR, "ffmpeg_extract")
    try:
        print("  [*] Downloading FFmpeg essentials for Windows...")
        _download_file(FFMPEG_WIN_URL, tmp_zip, "FFmpeg")
        if os.path.exists(tmp_extract):
            shutil.rmtree(tmp_extract, ignore_errors=True)
        _safe_extract_zip(tmp_zip, tmp_extract)

        copied = 0
        for root, _, files in os.walk(tmp_extract):
            for fname in files:
                if fname.lower() in ("ffmpeg.exe", "ffprobe.exe"):
                    shutil.copy2(os.path.join(root, fname), os.path.join(BIN_DIR, fname))
                    copied += 1

        ffmpeg_bin = hw.find_binary("ffmpeg")
        ffprobe_bin = hw.find_binary("ffprobe")
        if copied >= 2 and _binary_runs(ffmpeg_bin, "-version") and _binary_runs(ffprobe_bin, "-version"):
            hw.FFMPEG_BIN = ffmpeg_bin
            hw.FFPROBE_BIN = ffprobe_bin
            return {"status": "ready", "ffmpeg": ffmpeg_bin, "ffprobe": ffprobe_bin}
        return {"status": "error", "error": "FFmpeg extracted but failed verification"}
    except Exception as e:
        print(f"  [WARN] FFmpeg auto-install failed (offline or blocked): {e}")
        return {"status": "error", "error": str(e)}
    finally:
        for p in (tmp_zip, tmp_extract):
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _extract_release_bins(zip_path: str, dest_dir: str) -> None:
    """Extracts all .exe and .dll files from a release zip flat into dest_dir."""
    os.makedirs(dest_dir, exist_ok=True)
    tmp_extract = os.path.join(TEMP_DIR, f"whisper_extract_{int(time.time())}")
    try:
        _safe_extract_zip(zip_path, tmp_extract)
        for root, _, files in os.walk(tmp_extract):
            for fname in files:
                if fname.lower().endswith((".exe", ".dll")):
                    shutil.copy2(os.path.join(root, fname), os.path.join(dest_dir, fname))
    finally:
        if os.path.isdir(tmp_extract):
            shutil.rmtree(tmp_extract, ignore_errors=True)


def ensure_whisper_cli() -> Dict[str, Any]:
    """
    Ensures whisper-cli is available and passes `-h` smoke test.
    On Windows, auto-downloads CUDA build for dedicated NVIDIA GPUs (with VC++ Redistributable
    auto-install and CPU build fallback) or CPU build otherwise.
    """
    import backend.hardware as hw

    whisper_bin = hw.find_binary("whisper-cli", subdirs=["Release"])
    if _binary_runs(whisper_bin, "-h"):
        hw.WHISPER_CLI = whisper_bin
        return {"status": "ready", "path": whisper_bin}

    system = platform.system()
    if system != "Windows":
        hint = "brew install whisper-cpp" if system == "Darwin" else "Build whisper.cpp and place whisper-cli in bin/Release/"
        print(f"  [WARN] whisper-cli not found. {hint}")
        return {"status": "missing", "hint": hint}

    os.makedirs(RELEASE_BIN_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    tmp_zip = os.path.join(TEMP_DIR, "whisper-cli-win.zip")
    tmp_cpu_zip = os.path.join(TEMP_DIR, "whisper-cli-cpu-win.zip")

    try:
        req = urllib.request.Request(
            WHISPER_RELEASES_API,
            headers={"User-Agent": "Mozilla/5.0 OpenShorts/1.0", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            rel_data = json.loads(resp.read().decode("utf-8"))

        assets = rel_data.get("assets", [])
        cpu_url = None
        cuda_url = None
        for a in assets:
            name = str(a.get("name", "")).lower()
            dl_url = a.get("browser_download_url")
            if not dl_url or not name.endswith(".zip"):
                continue
            if name == "whisper-bin-x64.zip":
                cpu_url = dl_url
            elif "whisper-cublas-12." in name and name.endswith("-bin-x64.zip"):
                cuda_url = dl_url
            elif not cuda_url and "whisper-cublas-" in name and name.endswith("-bin-x64.zip"):
                cuda_url = dl_url

        gpu = hw.get_gpu_info()
        use_cuda = (gpu.get("vendor") == "NVIDIA" and gpu.get("is_dedicated", False) and bool(cuda_url))
        chosen_url = cuda_url if use_cuda else cpu_url
        if not chosen_url:
            return {"status": "error", "error": "No matching whisper.cpp Windows asset found"}

        label = "whisper-cli (CUDA)" if use_cuda else "whisper-cli (CPU)"
        print(f"  [*] Downloading {label}...")
        _download_file(chosen_url, tmp_zip, label)
        _extract_release_bins(tmp_zip, RELEASE_BIN_DIR)

        whisper_bin = hw.find_binary("whisper-cli", subdirs=["Release"])
        if not _binary_runs(whisper_bin, "-h"):
            # Try silent VC++ Redistributable install once if winget is available
            if shutil.which("winget"):
                print("  [*] Installing Microsoft VC++ 2015-2022 Redistributable...")
                try:
                    subprocess.run(
                        [
                            "winget", "install", "-e", "--id", "Microsoft.VCRedist.2015+.x64",
                            "--silent", "--accept-package-agreements", "--accept-source-agreements",
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=120,
                    )
                except Exception:
                    pass

        if not _binary_runs(whisper_bin, "-h") and use_cuda and cpu_url:
            print("  [WARN] CUDA whisper-cli smoke test failed; falling back to CPU build...")
            _download_file(cpu_url, tmp_cpu_zip, "whisper-cli (CPU fallback)")
            for stale_name in os.listdir(RELEASE_BIN_DIR):
                if stale_name.lower().endswith(".dll") or stale_name.lower() == "whisper-cli.exe":
                    try:
                        os.remove(os.path.join(RELEASE_BIN_DIR, stale_name))
                    except OSError:
                        pass
            _extract_release_bins(tmp_cpu_zip, RELEASE_BIN_DIR)
            whisper_bin = hw.find_binary("whisper-cli", subdirs=["Release"])

        if _binary_runs(whisper_bin, "-h"):
            hw.WHISPER_CLI = whisper_bin
            return {"status": "ready", "path": whisper_bin}
        return {"status": "error", "error": "whisper-cli failed smoke test after extraction"}
    except Exception as e:
        print(f"  [WARN] whisper-cli auto-install failed (offline or blocked): {e}")
        return {"status": "error", "error": str(e)}
    finally:
        for p in (tmp_zip, tmp_cpu_zip):
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _find_ollama_bin() -> Optional[str]:
    """Locates the ollama executable on PATH or default Windows install directory."""
    found = shutil.which("ollama")
    if found:
        return found
    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            candidate = os.path.join(local_app, "Programs", "Ollama", "ollama.exe")
            if os.path.isfile(candidate):
                return candidate
    return None


def ensure_ollama_and_model(auto_install: bool = True) -> Dict[str, Any]:
    """
    Ensures Ollama is installed, running, and has a hardware-matched Qwen3 model pulled.
    Never fails offline launches; cleanly falls back to built-in Cognitive NLP engine.
    """
    try:
        from backend.llm_engine import is_ollama_online, get_installed_llm_models
        from backend.hardware import get_performance_profile

        ollama_bin = _find_ollama_bin()
        system = platform.system()

        if not ollama_bin and auto_install:
            if system == "Windows":
                installed_ok = False
                if shutil.which("winget"):
                    print("  [*] Installing Ollama via winget...")
                    try:
                        res = subprocess.run(
                            [
                                "winget", "install", "-e", "--id", "Ollama.Ollama",
                                "--silent", "--accept-package-agreements", "--accept-source-agreements",
                            ],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=300,
                        )
                        installed_ok = (res.returncode == 0)
                    except Exception:
                        installed_ok = False

                if not installed_ok and not _find_ollama_bin():
                    os.makedirs(TEMP_DIR, exist_ok=True)
                    setup_exe = os.path.join(TEMP_DIR, "OllamaSetup.exe")
                    try:
                        print("  [*] Downloading OllamaSetup.exe...")
                        _download_file(OLLAMA_WIN_INSTALLER_URL, setup_exe, "Ollama")
                        print("  [*] Running silent Ollama installer...")
                        subprocess.run(
                            [setup_exe, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=300,
                        )
                    finally:
                        if os.path.isfile(setup_exe):
                            try:
                                os.remove(setup_exe)
                            except OSError:
                                pass
            elif system == "Darwin" and shutil.which("brew"):
                print("  [*] Installing Ollama via Homebrew...")
                subprocess.run(["brew", "install", "ollama"], timeout=300)
            else:
                print("  [INFO] Ollama not installed; skipping auto-install on Linux (Cognitive NLP fallback active).")
                return {"status": "skipped", "reason": "not_installed"}

        ollama_bin = _find_ollama_bin()
        if not ollama_bin:
            return {"status": "skipped", "reason": "ollama_unavailable"}

        if not is_ollama_online(timeout=1.5):
            print("  [*] Starting Ollama background service...")
            popen_kwargs: Dict[str, Any] = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "stdin": subprocess.DEVNULL,
            }
            if system == "Windows":
                popen_kwargs["creationflags"] = (
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "DETACHED_PROCESS", 0)
                )
            else:
                popen_kwargs["start_new_session"] = True
            subprocess.Popen([ollama_bin, "serve"], **popen_kwargs)

            for _ in range(16):
                time.sleep(0.5)
                if is_ollama_online(timeout=1.0):
                    break

        if not is_ollama_online(timeout=1.5):
            print("  [WARN] Ollama daemon did not respond in time (Cognitive NLP fallback active).")
            return {"status": "offline"}

        installed_models = get_installed_llm_models(timeout=3.0)
        if not installed_models:
            llm_tier = get_performance_profile().get("llm_tier", "standard")
            target_model = "qwen3:4b" if llm_tier == "compact" else "qwen3:8b"
            print(f"  [*] Pulling hardware-matched LLM ({target_model})...")
            subprocess.run([ollama_bin, "pull", target_model], timeout=1800)
            installed_models = get_installed_llm_models(timeout=3.0)

        return {"status": "ready", "models": installed_models}
    except Exception as e:
        print(f"  [INFO] Ollama setup skipped ({e}); built-in Cognitive NLP engine active.")
        return {"status": "skipped", "error": str(e)}


def run_full_first_time_setup(skip_ollama: bool = False) -> Dict[str, Any]:
    """
    Runs the complete zero-touch first-time setup in strict dependency order:
    1. FFmpeg & FFprobe
    2. whisper-cli
    3. Tier-gated Real-ESRGAN
    4. Hardware-matched Whisper GGML model (only if none present)
    5. Studio Flow font (Montserrat-ExtraBold.ttf)
    6. Ollama + hardware-matched Qwen3 model (unless skipped)
    """
    results: Dict[str, Any] = {}

    results["ffmpeg"] = ensure_ffmpeg()
    results["whisper_cli"] = ensure_whisper_cli()

    from backend.hardware import ensure_realesrgan_for_tier, get_performance_profile
    results["realesrgan"] = ensure_realesrgan_for_tier()

    perf = get_performance_profile()
    from backend.transcriber import ensure_whisper_model
    turbo_p = os.path.join(MODELS_DIR, "ggml-large-v3-turbo-q5_0.bin")
    small_p = os.path.join(MODELS_DIR, "ggml-small.en.bin")
    has_turbo = os.path.isfile(turbo_p) and os.path.getsize(turbo_p) > 1_000_000
    has_small = os.path.isfile(small_p) and os.path.getsize(small_p) > 1_000_000
    if has_turbo or has_small:
        results["whisper_model"] = {"status": "ready", "path": turbo_p if has_turbo else small_p}
    else:
        try:
            target_w = perf.get("whisper_model", "small.en")
            mpath = ensure_whisper_model(target_w)
            results["whisper_model"] = {"status": "ready", "path": mpath}
        except Exception as e:
            results["whisper_model"] = {"status": "error", "error": str(e)}

    from backend.subtitle_generator import ensure_skyglow_font
    try:
        fam, fdir = ensure_skyglow_font()
        results["font"] = {"status": "ready", "family": fam, "dir": fdir}
    except Exception as e:
        results["font"] = {"status": "error", "error": str(e)}

    env_skip = os.environ.get("OPENSHORTS_SKIP_OLLAMA", "").strip() == "1"
    if skip_ollama or env_skip:
        results["ollama"] = {"status": "skipped", "reason": "disabled_by_user"}
    else:
        results["ollama"] = ensure_ollama_and_model(auto_install=True)

    return results
