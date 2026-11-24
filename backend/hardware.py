"""
OpenShorts Hardware Auto-Detection & Adaptive Hardware Acceleration Engine.
Detects CPU model/threads, GPU vendors, VRAM, and RAM, dynamically probes FFmpeg for available
hardware encoders (NVIDIA NVENC, Intel QuickSync QSV, AMD AMF, Apple VideoToolbox, Linux VA-API, or CPU libx264),
and calculates an auto-adaptive performance tier (ultra, performance, balanced, eco).
Also provides portable path discovery for bundled binaries (ffmpeg, ffprobe, whisper-cli).
"""

import os
import sys
import platform
import subprocess
import shutil
import struct
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BIN_DIR = os.path.join(BASE_DIR, "bin")

def find_binary(bin_name: str, subdirs: Optional[List[str]] = None) -> str:
    """
    Finds executable binary in bundled directories, system PATH, or fallback locations.
    Cross-platform support for Windows, Linux, and macOS.
    """
    is_win = platform.system() == "Windows"
    exts = [".exe", ".cmd", ".bat"] if is_win else [""]
    
    # 1. Check local project bin/ and subdirs (Release/, etc.)
    search_dirs = [BIN_DIR]
    if subdirs:
        for sub in subdirs:
            search_dirs.append(os.path.join(BIN_DIR, sub))
    search_dirs.append(os.path.join(BIN_DIR, "Release"))
    
    for d in search_dirs:
        for ext in exts:
            candidate = os.path.join(d, bin_name + ext)
            if os.path.isfile(candidate):
                return candidate
            candidate_raw = os.path.join(d, bin_name)
            if os.path.isfile(candidate_raw):
                return candidate_raw

    # 2. Check System PATH
    found = shutil.which(bin_name)
    if found:
        return found
    if is_win:
        found_exe = shutil.which(f"{bin_name}.exe")
        if found_exe:
            return found_exe

    # 3. Common system fallbacks
    if is_win:
        winget_fallback = os.path.expanduser(
            r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin"
        )
        for ext in exts:
            c = os.path.join(winget_fallback, bin_name + ext)
            if os.path.isfile(c):
                return c
    else:
        for common_path in ["/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"]:
            c = os.path.join(common_path, bin_name)
            if os.path.isfile(c):
                return c

    # Fallback to bare name
    return bin_name + (".exe" if is_win else "")

# Global resolved binary paths
FFMPEG_BIN = find_binary("ffmpeg")
FFPROBE_BIN = find_binary("ffprobe")
WHISPER_CLI = find_binary("whisper-cli", subdirs=["Release"])
REALESRGAN_BIN = find_binary("realesrgan-ncnn-vulkan", subdirs=["realesrgan", "Release"])

def get_cpu_info() -> Dict[str, Any]:
    """Detects CPU model, core counts, and recommended thread allocations."""
    cores = os.cpu_count() or 4
    model = platform.processor() or "Multi-Core Processor"
    arch = platform.machine()
    system = platform.system()

    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if val and val.strip():
                model = val.strip()
        except Exception:
            try:
                cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"]
                out = subprocess.check_output(cmd, text=True, timeout=8).strip()
                if out:
                    model = out.splitlines()[0].strip()
            except Exception:
                pass
    elif system == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        model = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    elif system == "Darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True, timeout=3).strip()
            if out:
                model = out
        except Exception:
            pass

    return {
        "model": model,
        "cores": cores,
        "threads": cores,
        "arch": arch,
        "whisper_threads": max(1, min(cores, 8)),
        "ffmpeg_threads": max(1, min(cores, 16))
    }

# Cache for RAM detection
_RAM_CACHE: Optional[Dict[str, Any]] = None

def get_ram_info(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Detects total and available system RAM in gigabytes (GB) using zero external pip packages.
    Cross-platform support for Windows (ctypes GlobalMemoryStatusEx), Linux (/proc/meminfo),
    and macOS (sysctl hw.memsize).
    """
    global _RAM_CACHE
    if _RAM_CACHE is not None and not force_refresh:
        return _RAM_CACHE

    total_gb = 8.0
    available_gb = 4.0
    system = platform.system()

    if system == "Windows":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
                available_gb = round(stat.ullAvailPhys / (1024 ** 3), 1)
        except Exception:
            pass
    elif system == "Linux":
        try:
            mem_total_kb = 0
            mem_avail_kb = 0
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail_kb = int(line.split()[1])
            if mem_total_kb > 0:
                total_gb = round(mem_total_kb / (1024 * 1024), 1)
            if mem_avail_kb > 0:
                available_gb = round(mem_avail_kb / (1024 * 1024), 1)
            else:
                available_gb = round(total_gb * 0.5, 1)
        except Exception:
            pass
    elif system == "Darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=2).strip()
            if out and out.isdigit():
                total_gb = round(int(out) / (1024 ** 3), 1)
                available_gb = round(total_gb * 0.5, 1)
        except Exception:
            pass

    res = {
        "total_gb": total_gb,
        "available_gb": available_gb
    }
    _RAM_CACHE = res
    return res

# Cache for GPU info
_GPU_CACHE: Optional[Dict[str, Any]] = None

def get_gpu_info(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Detects installed graphics hardware, prioritizes dedicated GPUs,
    and detects dedicated/usable VRAM in GB.
    """
    global _GPU_CACHE
    if _GPU_CACHE is not None and not force_refresh:
        return _GPU_CACHE

    gpus: List[str] = []
    vram_gb: float = 0.0
    system = platform.system()

    if system == "Windows":
        # 1. Fast Registry lookup (0.001s, no subprocess delay)
        try:
            import winreg
            class_key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, 
                r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            )
            idx = 0
            while True:
                try:
                    sub = winreg.EnumKey(class_key, idx)
                    idx += 1
                    if sub.isdigit():
                        dev_key = winreg.OpenKey(class_key, sub)
                        try:
                            driver_desc, _ = winreg.QueryValueEx(dev_key, "DriverDesc")
                            if driver_desc and driver_desc not in gpus:
                                gpus.append(driver_desc)
                            # Probe VRAM in registry
                            for key_name in ["HardwareInformation.qwMemorySize", "HardwareInformation.MemorySize", "AdapterRAM"]:
                                try:
                                    val, _ = winreg.QueryValueEx(dev_key, key_name)
                                    if isinstance(val, bytes):
                                        if len(val) == 8:
                                            val = struct.unpack("<Q", val)[0]
                                        elif len(val) == 4:
                                            val = struct.unpack("<I", val)[0]
                                    if isinstance(val, (int, float)) and val > 0:
                                        cur_gb = round(val / (1024 ** 3), 1)
                                        if cur_gb > vram_gb:
                                            vram_gb = cur_gb
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except OSError:
                    break
        except Exception:
            pass

        # 2. Try nvidia-smi if NVIDIA is installed
        if any("nvidia" in g.lower() or "geforce" in g.lower() or "rtx" in g.lower() for g in gpus):
            try:
                cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
                out = subprocess.check_output(cmd, text=True, timeout=2).strip()
                if out:
                    val_mb = float(out.splitlines()[0].strip())
                    nv_gb = round(val_mb / 1024.0, 1)
                    if nv_gb > 0.0:
                        vram_gb = nv_gb
            except Exception:
                pass

        # 3. PowerShell fallback if registry is empty
        if not gpus:
            try:
                cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -Property Name, AdapterRAM | ConvertTo-Json"]
                out = subprocess.check_output(cmd, text=True, timeout=5).strip()
                if out:
                    import json
                    parsed = json.loads(out)
                    items = parsed if isinstance(parsed, list) else [parsed]
                    for it in items:
                        name = it.get("Name")
                        if name and name not in gpus:
                            gpus.append(name)
                        aram = it.get("AdapterRAM")
                        if aram and isinstance(aram, (int, float)) and aram > 0:
                            cur_gb = round(aram / (1024 ** 3), 1)
                            if cur_gb > vram_gb:
                                vram_gb = cur_gb
            except Exception:
                pass

    elif system == "Linux":
        try:
            out = subprocess.check_output(["lspci"], text=True, timeout=3)
            for line in out.splitlines():
                if "VGA" in line or "3D" in line:
                    gpus.append(line.split(":", 2)[-1].strip())
        except Exception:
            pass
        # Try nvidia-smi on Linux
        try:
            cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
            out = subprocess.check_output(cmd, text=True, timeout=2).strip()
            if out:
                val_mb = float(out.splitlines()[0].strip())
                vram_gb = round(val_mb / 1024.0, 1)
        except Exception:
            pass

    elif system == "Darwin":
        try:
            cmd = ["system_profiler", "SPDisplaysDataType"]
            out = subprocess.check_output(cmd, text=True, timeout=4)
            for line in out.splitlines():
                if "Chipset Model:" in line:
                    gpus.append(line.split(":", 1)[1].strip())
        except Exception:
            pass
        # Apple Silicon unified memory estimate
        if platform.machine() in ("arm64", "aarch64"):
            ram = get_ram_info()
            vram_gb = round(ram.get("total_gb", 16.0) * 0.65, 1)

    if not gpus:
        gpus = ["Integrated / Standard Display Device"]

    def is_dedicated(name: str) -> bool:
        nl = name.lower()
        return any(k in nl for k in (
            "nvidia", "geforce", "rtx", "gtx", "quadro", "titan", 
            "radeon rx", "radeon pro", "discrete"
        ))

    dedicated = [g for g in gpus if is_dedicated(g)]
    primary = dedicated[0] if dedicated else gpus[0]

    vendor = "Generic"
    primary_lower = primary.lower()
    if "nvidia" in primary_lower or "geforce" in primary_lower or "quadro" in primary_lower or "rtx" in primary_lower:
        vendor = "NVIDIA"
    elif "intel" in primary_lower or "uhd" in primary_lower or "iris" in primary_lower or "arc" in primary_lower:
        vendor = "Intel"
    elif "amd" in primary_lower or "radeon" in primary_lower:
        vendor = "AMD"
    elif "apple" in primary_lower or "m1" in primary_lower or "m2" in primary_lower or "m3" in primary_lower or "m4" in primary_lower:
        vendor = "Apple"

    res = {
        "devices": gpus,
        "primary": primary,
        "vendor": vendor,
        "is_dedicated": bool(dedicated),
        "vram_gb": round(vram_gb, 1)
    }
    _GPU_CACHE = res
    return res

# Cache for hardware encoder probing
_ENCODER_CACHE: Optional[Dict[str, bool]] = None

def probe_hardware_encoders(force_refresh: bool = False) -> Dict[str, bool]:
    """
    Performs live 0.1-second test encodes via FFmpeg to definitively verify
    which hardware acceleration encoders are operational on this specific PC.
    Supports NVENC, QSV, AMF, Apple VideoToolbox, Linux VA-API, and CPU libx264.
    """
    global _ENCODER_CACHE
    if _ENCODER_CACHE is not None and not force_refresh:
        return _ENCODER_CACHE

    is_linux = platform.system() == "Linux"
    has_vaapi_device = is_linux and os.path.exists("/dev/dri/renderD128")

    encoders_to_test = ["h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"]
    if has_vaapi_device:
        encoders_to_test.append("h264_vaapi")
    encoders_to_test.append("libx264")

    results = {}

    for enc in encoders_to_test:
        try:
            if enc == "h264_vaapi":
                cmd = [
                    FFMPEG_BIN,
                    "-hide_banner",
                    "-loglevel", "error",
                    "-vaapi_device", "/dev/dri/renderD128",
                    "-f", "lavfi",
                    "-i", "color=c=black:s=256x256:d=0.1",
                    "-vf", "format=nv12,hwupload",
                    "-c:v", "h264_vaapi",
                    "-f", "null",
                    "-"
                ]
            else:
                cmd = [
                    FFMPEG_BIN,
                    "-hide_banner",
                    "-loglevel", "error",
                    "-f", "lavfi",
                    "-i", "color=c=black:s=256x256:d=0.1",
                    "-c:v", enc,
                    "-f", "null",
                    "-"
                ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            results[enc] = (res.returncode == 0)
        except Exception:
            results[enc] = False

    # libx264 is always available on our compiled FFmpeg
    if not results.get("libx264"):
        results["libx264"] = True

    _ENCODER_CACHE = results
    return results

def get_best_encoder() -> str:
    """
    Determines the fastest hardware encoder supported on the current machine.
    Hierarchy: NVIDIA NVENC -> Intel QuickSync -> AMD AMF -> Apple VideoToolbox -> Linux VA-API -> Multi-Core CPU (libx264).
    """
    probed = probe_hardware_encoders()
    if probed.get("h264_nvenc"):
        return "h264_nvenc"
    if probed.get("h264_qsv"):
        return "h264_qsv"
    if probed.get("h264_amf"):
        return "h264_amf"
    if probed.get("h264_videotoolbox"):
        return "h264_videotoolbox"
    if probed.get("h264_vaapi"):
        return "h264_vaapi"
    return "libx264"

def get_encoder_args(encoder: str, threads: Optional[int] = None, bitrate: Optional[str] = None) -> List[str]:
    """
    Returns optimal FFmpeg video encoding arguments for the selected encoder.
    Supports Topaz 4K Master bitrates (35M), 2K Ultra (20M), 1080p High (12M-15M), 8M, 5M.
    """
    cpu_info = get_cpu_info()
    t = str(threads or cpu_info["ffmpeg_threads"])
    target_bitrate = bitrate or "12M"
    
    is_ultra = any(b in target_bitrate for b in ("25M", "30M", "35M", "40M", "50M"))
    is_2k = "20M" in target_bitrate

    if encoder == "h264_nvenc":
        cq = "16" if is_ultra else ("18" if is_2k else "20")
        preset = "p5" if is_ultra else "p4"
        maxrate = "50M" if is_ultra else ("35M" if is_2k else "25M")
        bufsize = "80M" if is_ultra else ("50M" if is_2k else "35M")
        return [
            "-c:v", "h264_nvenc",
            "-gpu", "0",
            "-preset", preset,
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", cq,
            "-spatial-aq", "1",
            "-temporal-aq", "1",
            "-b:v", target_bitrate,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-pix_fmt", "yuv420p"
        ]
    elif encoder == "h264_qsv":
        gq = "16" if is_ultra else ("18" if is_2k else "20")
        preset = "medium" if is_ultra else "fast"
        maxrate = "50M" if is_ultra else ("35M" if is_2k else "25M")
        bufsize = "80M" if is_ultra else ("50M" if is_2k else "35M")
        return [
            "-c:v", "h264_qsv",
            "-preset", preset,
            "-b:v", target_bitrate,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-global_quality", gq,
            "-pix_fmt", "nv12"
        ]
    elif encoder == "h264_amf":
        qp = "15" if is_ultra else ("17" if is_2k else "20")
        return [
            "-c:v", "h264_amf",
            "-quality", "quality",
            "-rc", "cqp",
            "-qp_i", qp,
            "-qp_p", qp,
            "-b:v", target_bitrate,
            "-pix_fmt", "nv12"
        ]
    elif encoder == "h264_videotoolbox":
        return [
            "-c:v", "h264_videotoolbox",
            "-b:v", target_bitrate,
            "-pix_fmt", "yuv420p"
        ]
    elif encoder == "h264_vaapi":
        bufsize = "80M" if is_ultra else ("50M" if is_2k else "35M")
        return [
            "-c:v", "h264_vaapi",
            "-b:v", target_bitrate,
            "-maxrate", target_bitrate,
            "-bufsize", bufsize
        ]
    else:  # libx264 fallback
        crf = "16" if is_ultra else ("18" if is_2k else "20")
        preset = "fast"
        maxrate = "50M" if is_ultra else ("35M" if is_2k else "25M")
        bufsize = "80M" if is_ultra else ("50M" if is_2k else "35M")
        return [
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", crf,
            "-b:v", target_bitrate,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-pix_fmt", "yuv420p",
            "-threads", t
        ]

# Cache for performance profile
_PERF_PROFILE_CACHE: Optional[Dict[str, Any]] = None

def get_performance_profile(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Classifies the system into one of 4 auto-adaptive tiers:
    - 'ultra': Dedicated GPU with vram_gb >= 8 (or Apple Silicon >= 24GB) AND cores >= 8 AND ram_gb >= 16
    - 'performance': Dedicated GPU with vram_gb >= 4 OR (cores >= 8 and ram_gb >= 16)
    - 'balanced': Hardware iGPU (qsv/amf/vaapi/videotoolbox) OR (cores >= 6 and ram_gb >= 12)
    - 'eco': CPU-only / < 12 GB RAM / <= 4 cores
    Returns concrete tuning parameters for concurrency, filters, bitrates, Whisper, and LLMs.
    """
    global _PERF_PROFILE_CACHE
    if _PERF_PROFILE_CACHE is not None and not force_refresh:
        return _PERF_PROFILE_CACHE

    cpu = get_cpu_info()
    gpu = get_gpu_info()
    ram = get_ram_info()
    best_enc = get_best_encoder()

    cores = int(cpu.get("cores", 4))
    ram_gb = float(ram.get("total_gb", 8.0))
    vram_gb = float(gpu.get("vram_gb", 0.0))
    is_dedicated = bool(gpu.get("is_dedicated", False))
    is_hw_enc = best_enc in ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox", "h264_vaapi")
    is_apple_silicon = gpu.get("vendor") == "Apple" and platform.system() == "Darwin"

    # Tier Classification
    if ((is_dedicated and vram_gb >= 8.0) or (is_apple_silicon and ram_gb >= 24.0)) and (cores >= 8) and (ram_gb >= 16.0):
        tier = "ultra"
        export_workers = 3
        filter_mode = "ultra"
        default_1080p_bitrate = "15M"
        whisper_model = "base.en"
        llm_tier = "large"
    elif ((is_hw_enc and (is_dedicated or vram_gb >= 4.0)) and vram_gb >= 4.0) or (cores >= 8 and ram_gb >= 16.0):
        tier = "performance"
        export_workers = 2
        filter_mode = "balanced"
        default_1080p_bitrate = "14M"
        whisper_model = "base.en"
        llm_tier = "standard"
    elif is_hw_enc or (cores >= 6 and ram_gb >= 12.0):
        tier = "balanced"
        export_workers = 1
        filter_mode = "fast"
        default_1080p_bitrate = "12M"
        whisper_model = "base.en"
        llm_tier = "compact" if (ram_gb < 12.0 and not is_dedicated) else "standard"
    else:
        tier = "eco"
        export_workers = 1
        filter_mode = "eco"
        default_1080p_bitrate = "10M"
        whisper_model = "tiny.en"
        llm_tier = "compact"

    profile = {
        "tier": tier,
        "export_workers": export_workers,
        "filter_mode": filter_mode,
        "default_1080p_bitrate": default_1080p_bitrate,
        "whisper_model": whisper_model,
        "llm_tier": llm_tier,
        "ram_gb": ram_gb,
        "vram_gb": vram_gb,
        "cores": cores,
        "best_encoder": best_enc
    }
    _PERF_PROFILE_CACHE = profile
    return profile

def get_hardware_profile() -> Dict[str, Any]:
    """
    Returns complete hardware specification, RAM, performance profile,
    and acceleration capabilities for the UI and backend processing.
    """
    cpu = get_cpu_info()
    gpu = get_gpu_info()
    ram = get_ram_info()
    perf = get_performance_profile()
    probed = probe_hardware_encoders()
    best_enc = get_best_encoder()

    encoder_labels = {
        "h264_nvenc": "⚡ NVIDIA NVENC GPU Acceleration (Ultra-Fast Hardware)",
        "h264_qsv": "⚡ Intel QuickSync QSV GPU (Hardware Accelerated)",
        "h264_amf": "⚡ AMD AMF Radeon GPU (Hardware Accelerated)",
        "h264_videotoolbox": "⚡ Apple Silicon VideoToolbox (Hardware Accelerated)",
        "h264_vaapi": "⚡ Linux VA-API GPU Acceleration (Hardware Accelerated)",
        "libx264": f"🚀 Ultrafast Multi-Core CPU ({cpu['cores']} Threads)"
    }

    encoders_list = []
    for enc_id, label in encoder_labels.items():
        is_avail = probed.get(enc_id, False)
        is_rec = (enc_id == best_enc)
        encoders_list.append({
            "id": enc_id,
            "label": label,
            "available": is_avail,
            "recommended": is_rec,
            "type": "gpu" if enc_id != "libx264" else "cpu"
        })

    # Badge text for header / UI
    if best_enc == "h264_nvenc":
        badge = "⚡ NVIDIA NVENC (Active)"
    elif best_enc == "h264_qsv":
        badge = "⚡ Intel QuickSync (Active)"
    elif best_enc == "h264_amf":
        badge = "⚡ AMD AMF (Active)"
    elif best_enc == "h264_videotoolbox":
        badge = "⚡ Apple VideoToolbox (Active)"
    elif best_enc == "h264_vaapi":
        badge = "⚡ Linux VA-API (Active)"
    else:
        badge = f"🚀 Multi-Core CPU ({cpu['cores']}T)"

    return {
        "cpu": cpu,
        "gpu": gpu,
        "ram": ram,
        "performance_profile": perf,
        "available_encoders": probed,
        "encoders_list": encoders_list,
        "recommended_encoder": best_enc,
        "status_badge": badge,
        "binary_paths": {
            "ffmpeg": FFMPEG_BIN,
            "ffprobe": FFPROBE_BIN,
            "whisper": WHISPER_CLI,
            "realesrgan": REALESRGAN_BIN
        },
        "has_realesrgan": bool(os.path.isfile(REALESRGAN_BIN))
    }
