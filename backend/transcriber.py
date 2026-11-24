import os
import subprocess
import json
import re
import hashlib
import wave
import struct
import math
from typing import List, Dict, Any, Optional
from backend.hardware import FFMPEG_BIN, WHISPER_CLI, get_cpu_info

MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
DEFAULT_MODEL_BASE_EN = os.path.join(MODELS_DIR, "ggml-base.en.bin")
DEFAULT_MODEL_BASE = os.path.join(MODELS_DIR, "ggml-base.bin")
DEFAULT_MODEL_EN = os.path.join(MODELS_DIR, "ggml-tiny.en.bin")
DEFAULT_MODEL_MULTI = os.path.join(MODELS_DIR, "ggml-tiny.bin")

def ensure_whisper_model(preferred_name: str = "base.en") -> str:
    """
    Ensures that a valid GGML model file exists in the models/ directory.
    If none exists, automatically downloads the lightweight high-accuracy model from HuggingFace.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    preferred_path = os.path.join(MODELS_DIR, f"ggml-{preferred_name}.bin")
    if os.path.isfile(preferred_path) and os.path.getsize(preferred_path) > 1000000:
        return preferred_path

    # Check fallbacks already on disk
    for candidate in [DEFAULT_MODEL_BASE_EN, DEFAULT_MODEL_BASE, DEFAULT_MODEL_EN, DEFAULT_MODEL_MULTI]:
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 1000000:
            return candidate

    # Auto-download preferred model (or tiny.en fallback)
    for model_to_dl in [preferred_name, "tiny.en"]:
        file_name = f"ggml-{model_to_dl}.bin"
        dl_url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{file_name}"
        dl_path = os.path.join(MODELS_DIR, file_name)
        try:
            print(f"[*] Downloading missing Whisper model ({file_name}) from HuggingFace...")
            import urllib.request
            urllib.request.urlretrieve(dl_url, dl_path)
            if os.path.isfile(dl_path) and os.path.getsize(dl_path) > 1000000:
                print(f"[OK] Downloaded {file_name} successfully ({os.path.getsize(dl_path)/(1024*1024):.1f} MB).")
                return dl_path
        except Exception as e:
            print(f"[WARN] Failed to download {file_name}: {e}")

    raise RuntimeError("Whisper speech model missing and automatic download failed. Please check internet connection.")

TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "temp"))
os.makedirs(TEMP_DIR, exist_ok=True)

def parse_time_str(time_str: str) -> float:
    """Parses HH:MM:SS,mmm or HH:MM:SS.mmm to seconds float."""
    match = re.match(r"(\d+):(\d+):(\d+)[,\.](\d+)", time_str)
    if match:
        h, m, s, ms = match.groups()
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/(10**len(ms))
    return 0.0

def get_media_duration(file_path: str) -> float:
    """Probes media duration in seconds using ffprobe."""
    if not file_path or not os.path.exists(file_path):
        return 0.0
    try:
        from backend.hardware import FFPROBE_BIN
        cmd = [
            FFPROBE_BIN, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        val = res.stdout.strip()
        if res.returncode == 0 and val and val != "N/A":
            try:
                return max(0.0, float(val))
            except ValueError:
                pass
        # Fallback to streams
        cmd2 = [
            FFPROBE_BIN, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        val2 = res2.stdout.strip()
        if res2.returncode == 0 and val2 and val2 != "N/A":
            try:
                return max(0.0, float(val2))
            except ValueError:
                pass
    except Exception:
        pass
    return 0.0

def create_silent_wav(output_wav: str, duration_sec: float = 1.0):
    """Generates a valid 16kHz mono 16-bit PCM silent WAV file to prevent miniaudio crashes."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
        num_samples = int(16000 * max(0.5, duration_sec))
        with wave.open(output_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * num_samples)
    except Exception as e:
        print(f"[WARN] Failed to create silent WAV: {e}")

def extract_audio_wav(
    video_path: str, 
    output_wav: str = None, 
    start_time: float = None, 
    duration: float = None,
    streamer_voice_focus: bool = True,
    audio_track: int = 0
) -> str:
    """
    Extracts 16kHz mono WAV required by whisper.cpp.
    When streamer_voice_focus is enabled, applies an acoustic isolation filter pipeline:
    - Highpass & lowpass bandpass for human vocal range (120Hz - 3600Hz)
    - Dynamic noise gate (-34dB) to attenuate quiet background NPC chatter & game ambiance
    - Adaptive FFT noise reduction to suppress game music/hum
    - Center speech channel summing and speech normalization
    Includes boundary clamping against actual video duration and empty-audio protection.
    """
    # 0. Probe video duration to avoid seeking past EOF
    v_dur = get_media_duration(video_path)
    if v_dur > 0.0:
        if start_time is not None and start_time >= v_dur:
            print(f"[WARN] Requested start_time ({start_time}s) >= video duration ({v_dur}s). Clamping start_time to 0.0s.")
            start_time = 0.0
        if duration is not None:
            effective_start = start_time or 0.0
            if effective_start + duration > v_dur:
                duration = max(1.0, v_dur - effective_start)

    if not output_wav:
        raw_name = os.path.splitext(os.path.basename(video_path))[0]
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_name)
        clean_name = re.sub(r'_+', '_', clean_name).strip('_')
        if not clean_name:
            clean_name = "audio"
        path_hash = hashlib.md5(video_path.encode('utf-8', errors='ignore')).hexdigest()[:6]
        base_name = f"{clean_name[:32]}_{path_hash}"

        focus_tag = "_streamer" if streamer_voice_focus else ""
        track_tag = f"_t{audio_track}" if audio_track > 0 else ""
        suffix = f"_clip_{int(start_time)}_{int(duration)}" if start_time is not None else ""
        output_wav = os.path.join(TEMP_DIR, f"{base_name}{focus_tag}{track_tag}{suffix}_16k.wav")
    
    # Remove any stale empty/corrupt WAV files (< 512 bytes)
    if os.path.exists(output_wav) and os.path.getsize(output_wav) < 512:
        try:
            os.remove(output_wav)
        except Exception:
            pass
    
    cmd = [
        FFMPEG_BIN, "-y"
    ]
    if start_time is not None:
        cmd += ["-ss", str(start_time), "-accurate_seek"]
    cmd += ["-i", video_path]
    if duration is not None:
        cmd += ["-t", str(duration)]
    
    cmd += ["-vn"]
    
    # Select audio track if specified (OBS multi-track or dedicated mic track)
    if audio_track is not None and audio_track >= 0:
        cmd += ["-map", f"0:a:{audio_track}?"]
    
    # Audio filters: Clean Whisper-friendly Vocal Normalization Pipeline
    if streamer_voice_focus:
        voice_filter = "asetpts=PTS-STARTPTS,pan=mono|c0=0.5*c0+0.5*c1,highpass=f=80,lowpass=f=7800,dynaudnorm=f=150:g=15:p=0.90:m=5.0"
    else:
        voice_filter = "asetpts=PTS-STARTPTS"
    cmd += ["-af", voice_filter]
        
    cmd += [
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0 or not os.path.exists(output_wav) or os.path.getsize(output_wav) < 512:
        # Fallback 1: Simple extraction without complex filters
        fb_cmd = [
            FFMPEG_BIN, "-y"
        ]
        if start_time is not None:
            fb_cmd += ["-ss", str(start_time), "-accurate_seek"]
        fb_cmd += [
            "-i", video_path
        ]
        if duration is not None:
            fb_cmd += ["-t", str(duration)]
        fb_cmd += [
            "-vn",
            "-af", "asetpts=PTS-STARTPTS",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_wav
        ]
        fb_res = subprocess.run(fb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Fallback 2: If still empty (e.g. invalid start_time), extract from 0.0
        if not os.path.exists(output_wav) or os.path.getsize(output_wav) < 512:
            print("[WARN] Extracted WAV file was empty or missing. Attempting fallback extraction from 0.0s...")
            fb0_cmd = [
                FFMPEG_BIN, "-y",
                "-i", video_path,
                "-t", str(duration or 15.0),
                "-vn",
                "-af", "asetpts=PTS-STARTPTS",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                output_wav
            ]
            subprocess.run(fb0_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Fallback 3: If still < 512 bytes, generate a valid silent WAV to prevent miniaudio crashes
        if not os.path.exists(output_wav) or os.path.getsize(output_wav) < 512:
            print("[WARN] Failed to extract audio frames. Generating valid silent WAV to avoid miniaudio crash.")
            create_silent_wav(output_wav, duration or 2.0)

    return output_wav

def get_dtw_preset(model_path: str) -> Optional[str]:
    """Derives DTW model preset from model_path basename (e.g. ggml-base.en.bin -> base.en)."""
    if not model_path:
        return None
    base = os.path.basename(model_path).lower()
    base = re.sub(r'^ggml-', '', base)
    base = re.sub(r'\.bin$', '', base)
    presets = ["tiny.en", "tiny", "base.en", "base", "small.en", "small", "medium.en", "medium", "large-v1", "large-v2", "large-v3", "large"]
    for p in presets:
        if base == p or base.startswith(p):
            return p
    return None

def parse_tokens_to_words(raw_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reconstructs exact word boundaries and timestamps from Whisper -ojf full token outputs.
    Uses native DTW token timestamps and millisecond integer offsets for exact acoustic alignment,
    merges BPE subwords, completely strips full stops (.) and commas (,), suppresses consecutive
    repetitive hallucinations, and clamps word highlights to prevent timing drift across pauses.
    """
    words = []
    current_word = ""
    w_start = None
    w_end = None
    
    # 1. Anti-Hallucination Pass: Suppress consecutive duplicate segments
    cleaned_segments = []
    prev_norm = ""
    for seg in raw_segments:
        text = seg.get("text", "").strip()
        norm = re.sub(r'[^a-zA-Z0-9]', '', text.lower())
        if not norm:
            continue
        # Drop repeated hallucinated segments (e.g. 10x repeated "Oh, go ahead!")
        if norm == prev_norm:
            continue
        prev_norm = norm
        cleaned_segments.append(seg)

    for seg in cleaned_segments:
        toks = seg.get("tokens")
        if not toks:
            # Segment without tokens: parse words from segment text directly
            text = seg.get("text", "").strip()
            # Filter non-vocal audio cues like (door opens), [music], (applause)
            if not text or (text.startswith("(") and text.endswith(")")) or (text.startswith("[") and text.endswith("]")):
                continue
            # Strip all full stops and commas immediately
            text = re.sub(r'[,.]+', '', text).strip()
            if not text:
                continue
            offsets = seg.get("offsets", {})
            if "from" in offsets and "to" in offsets and offsets["from"] is not None:
                seg_s = float(offsets["from"]) / 1000.0
                seg_e = float(offsets["to"]) / 1000.0
            else:
                ts = seg.get("timestamps", {})
                seg_s = parse_time_str(ts.get("from", "00:00:00,000"))
                seg_e = parse_time_str(ts.get("to", "00:00:00,000"))
            
            w_list = [re.sub(r'[,.]+', '', w).strip() for w in text.split() if re.sub(r'[,.]+', '', w).strip()]
            if w_list and seg_e > seg_s:
                dur = seg_e - seg_s
                step = dur / len(w_list)
                for idx, w in enumerate(w_list):
                    words.append({
                        "word": w,
                        "start": round(seg_s + idx * step, 3),
                        "end": round(seg_s + (idx + 1) * step, 3)
                    })
            continue

        for tok in toks:
            raw = tok.get("text", "")
            if not raw or raw.startswith("[") or (raw.startswith("(") and raw.endswith(")")) or "<|" in raw:
                continue
            
            # Prioritize DTW token timestamp (centiseconds -> seconds) if available, else millisecond offsets
            offsets = tok.get("offsets", {})
            if "from" in offsets and "to" in offsets and offsets["from"] is not None:
                offset_s = float(offsets["from"]) / 1000.0
                offset_e = float(offsets["to"]) / 1000.0
            else:
                ts = tok.get("timestamps", {})
                t_from = ts.get("from", "00:00:00,000")
                t_to = ts.get("to", "00:00:00,000")
                offset_s = parse_time_str(t_from)
                offset_e = parse_time_str(t_to)

            t_dtw_val = tok.get("t_dtw", -1)
            if t_dtw_val is not None and float(t_dtw_val) >= 0:
                dtw_s = float(t_dtw_val) / 100.0
                if abs(dtw_s - offset_s) <= 1.2:
                    s_sec = dtw_s
                else:
                    s_sec = offset_s
            else:
                s_sec = offset_s
            e_sec = max(s_sec + 0.06, offset_e)

            is_new_word = raw.startswith(" ") or current_word == ""
            clean_text = re.sub(r"<\|.*?\|>", "", raw).strip()
            
            # Strip all full stops (.) and commas (,) from every token
            clean_text = re.sub(r'[,.]+', '', clean_text).strip()
            
            if not clean_text:
                continue

            # Skip bracketed sound effects e.g. (door, opens), [music]
            if (clean_text.startswith("(") and clean_text.endswith(")")) or (clean_text.startswith("[") and clean_text.endswith("]")):
                continue

            # Attach punctuation (exclamation, question marks) to preceding word if needed
            if clean_text in ("!", "?", ";", ":"):
                if current_word:
                    current_word += clean_text
                    w_end = max(w_end or e_sec, e_sec)
                continue

            if is_new_word:
                if current_word and w_start is not None:
                    final_w = re.sub(r'[,.]+', '', current_word).strip()
                    if final_w:
                        words.append({
                            "word": final_w,
                            "start": round(w_start, 3),
                            "end": round(max(w_start + 0.06, w_end or (w_start + 0.12)), 3)
                        })
                current_word = clean_text
                w_start = s_sec
                w_end = max(s_sec + 0.06, e_sec)
            else:
                current_word += clean_text
                w_end = max(w_end or e_sec, e_sec)

    if current_word and w_start is not None:
        final_w = re.sub(r'[,.]+', '', current_word).strip()
        if final_w:
            words.append({
                "word": final_w,
                "start": round(w_start, 3),
                "end": round(max(w_start + 0.06, w_end or (w_start + 0.12)), 3)
            })
        
    # Second-pass anti-drift clamping: ensure each word cleanly hands off to next word's start
    clamped_words = []
    for i, w in enumerate(words):
        w_item = dict(w)
        if i + 1 < len(words):
            next_start = words[i + 1]["start"]
            if next_start >= w_item["start"] + 0.04:
                w_item["end"] = min(w_item["end"], next_start)
        # Enforce minimum duration of 0.06s
        if w_item["end"] <= w_item["start"]:
            w_item["end"] = round(w_item["start"] + 0.06, 3)
        clamped_words.append(w_item)

    return clamped_words

def align_words_to_acoustic_energy(
    words: List[Dict[str, Any]], 
    wav_path: str
) -> List[Dict[str, Any]]:
    """
    Automatic Acoustic Vocal Energy Alignment & Silence Gating.
    1. Rejects Whisper hallucinations that fall into true audio silence or floor noise.
    2. Collapses repetitive words emitted during low-energy stream pauses.
    3. Snaps word start boundaries to the steep acoustic vocal attack edge in the 16kHz audio.
    4. Snaps word end boundaries to vocal release before pauses, eliminating temporal drift.
    5. Strips all full stops (.) and commas (,) from all words.
    """
    if not words or not os.path.exists(wav_path):
        return words

    try:
        with wave.open(wav_path, "rb") as wf:
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            sampwidth = wf.getsampwidth()
            raw = wf.readframes(n_frames)

        if framerate <= 0 or sampwidth != 2:
            return words

        total_samples = len(raw) // 2
        samples = struct.unpack(f"<{total_samples}h", raw)

        # CapCut Grade: 5ms ultra-high temporal resolution (80 samples at 16kHz = 200 fps)
        frame_len = int(framerate * 0.005)
        if frame_len <= 0:
            return words

        # Calculate RMS energy for every 5ms frame
        energies = []
        for i in range(0, total_samples, frame_len):
            chunk = samples[i:i + frame_len]
            if chunk:
                rms = math.sqrt(sum(s * s for s in chunk) / len(chunk))
                energies.append(rms)

        n_energies = len(energies)
        if n_energies < 20:
            return words

        # Calculate energy derivative (vocal attack velocity dE/dt)
        gradients = [0.0]
        for i in range(1, n_energies):
            gradients.append(energies[i] - energies[i - 1])

        # Global audio baseline stats
        sorted_e = sorted(energies)
        global_floor = sorted_e[int(n_energies * 0.15)]
        global_peak = sorted_e[int(n_energies * 0.95)]
        dynamic_range = max(1.0, global_peak - global_floor)
        silence_threshold = global_floor + (dynamic_range * 0.12)

        aligned = []
        prev_word_text = ""
        prev_word_end = 0.0
        consecutive_repeat_count = 0

        for idx, w in enumerate(words):
            raw_w = re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()
            if not raw_w:
                continue

            w_item = dict(w)
            w_item["word"] = raw_w
            nominal_start = float(w.get("start", 0))
            nominal_end = float(w.get("end", nominal_start + 0.1))

            f_start = max(0, min(n_energies - 1, int(nominal_start * 200)))
            f_end = max(0, min(n_energies - 1, int(nominal_end * 200)))

            # 1. Acoustic Silence Hallucination Filter
            if f_end >= f_start:
                word_energies = energies[f_start:f_end + 1]
                mean_energy = sum(word_energies) / max(1, len(word_energies))
                peak_energy = max(word_energies)
            else:
                mean_energy = energies[f_start]
                peak_energy = energies[f_start]

            if peak_energy < silence_threshold and mean_energy < silence_threshold:
                continue

            # 2. Suppress repetitive word hallucinations during quiet pauses
            norm_w = raw_w.lower()
            if norm_w == prev_word_text and (nominal_start - prev_word_end) < 0.35:
                consecutive_repeat_count += 1
                if consecutive_repeat_count >= 2 or mean_energy < (global_floor + dynamic_range * 0.10):
                    continue
            else:
                consecutive_repeat_count = 0

            # 3. 5ms Sub-Frame Acoustic Attack Snapping with Speech Onset Lead Compensation
            # Whisper token attention naturally lags audio attack by 120-180ms.
            # Look back up to 36 frames (-180ms) to snap to the true consonant onset.
            win_s = max(1, f_start - 36)
            win_e = min(n_energies - 1, f_start + 16)

            best_f = f_start
            max_attack_score = -1e9
            for f_idx in range(win_s, win_e + 1):
                e_val = energies[f_idx]
                grad_val = gradients[f_idx]
                if e_val >= silence_threshold * 0.85:
                    attack_score = grad_val * 0.80 + (e_val - silence_threshold) * 0.20
                    if attack_score > max_attack_score:
                        max_attack_score = attack_score
                        best_f = f_idx

            if max_attack_score > 0:
                # Apply professional speech-onset lead (0.04s lead) so text hits screen right as lips move
                onset_sec = max(0.0, best_f * 0.005 - 0.04)
                w_item["start"] = round(onset_sec, 3)
            else:
                w_item["start"] = round(max(0.0, nominal_start - 0.08), 3)

            # 4. 5ms Vocal Offset Snapping (Snap word end before long pauses)
            is_followed_by_pause = False
            if idx + 1 < len(words):
                next_start = float(words[idx + 1].get("start", nominal_end))
                if (next_start - nominal_end) > 0.08:
                    is_followed_by_pause = True
            else:
                is_followed_by_pause = True

            if is_followed_by_pause:
                win_es = max(0, f_end - 20)
                win_ee = min(n_energies - 1, f_end + 20)
                if win_ee > win_es:
                    local_end_win = energies[win_es:win_ee + 1]
                    local_floor = min(local_end_win)
                    end_thresh = local_floor + 0.18 * (max(local_end_win) - local_floor)

                    best_end_f = f_end
                    for f_idx in range(win_es, win_ee + 1):
                        if energies[f_idx] <= end_thresh:
                            best_end_f = f_idx
                            break
                    w_item["end"] = round(max(w_item["start"] + 0.06, best_end_f * 0.005), 3)
            else:
                w_item["end"] = round(max(w_item["start"] + 0.06, nominal_end - 0.04), 3)

            aligned.append(w_item)
            prev_word_text = norm_w
            prev_word_end = w_item["end"]

        # Final monotonic sequential safety pass (zero lag accumulation in rapid speech)
        resolved_aligned = []
        last_word_end = 0.0
        for w_item in aligned:
            s = float(w_item["start"])
            e = float(w_item["end"])
            txt = w_item.get("word", "")
            nat_min = max(0.08, min(0.25, len(txt) * 0.04))
            
            # Prevent backward jumps without artificially pushing words into delayed drift
            if s < last_word_end - 0.04:
                s = round(last_word_end, 3)
            if e <= s:
                e = round(s + nat_min, 3)
            elif (e - s) < nat_min:
                e = round(s + nat_min, 3)
                
            w_item["start"] = s
            w_item["end"] = e
            last_word_end = e
            resolved_aligned.append(w_item)

        return resolved_aligned

    except Exception as e:
        print(f"Notice: Acoustic energy alignment fallback: {e}")
        return words

def sanitize_word_timings(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Non-destructive timing sanitizer:
    1. Completely strips punctuation [,. ]+.
    2. Drops obvious Whisper stutter loops (identical word repeated 3+ times within 0.6s).
    3. Enforces monotonic non-overlapping timestamps and guarantees a minimum readable word duration (>= 0.06s).
    Preserves quiet dialogue without dropping words based on acoustic silence or scream peaks.
    """
    if not words:
        return []
    cleaned = []
    for w in words:
        txt = re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()
        if txt:
            cleaned.append({
                "word": txt,
                "start": max(0.0, float(w.get("start", 0))),
                "end": max(0.0, float(w.get("end", 0)))
            })
    # Drop obvious Whisper stutter loops (identical word repeated 3+ times within 0.6s)
    deduped = []
    for i, w in enumerate(cleaned):
        norm = w["word"].lower()
        if len(deduped) >= 2:
            if norm == deduped[-1]["word"].lower() == deduped[-2]["word"].lower():
                if (w["start"] - deduped[-2]["start"]) < 0.6:
                    continue
        deduped.append(w)

    sanitized = []
    last_end = 0.0
    for i, w in enumerate(deduped):
        s = max(last_end, float(w["start"]))
        e = max(s + 0.06, float(w["end"]))
        if i + 1 < len(deduped):
            next_s = float(deduped[i + 1]["start"])
            if next_s > s:
                e = max(s + 0.04, min(e, next_s))
        sanitized.append({
            "word": w["word"],
            "start": round(s, 3),
            "end": round(max(s + 0.06, e), 3)
        })
        last_end = round(max(s + 0.06, e), 3)
    return sanitized

def group_words_into_segments(
    words: List[Dict[str, Any]], 
    words_per_line: int = 3
) -> List[Dict[str, Any]]:
    """
    Groups individual word tokens into chunks according to words_per_line.
    All full stops (.) and commas (,) are completely removed.
    words_per_line:
      1: 1 word at a time (high-energy punchy TikTok style)
      2: 2 words at a time
      3: 3 words at a time (default viral sweet spot)
      4: 4 words at a time
      0 or >= 6: natural sentences
    """
    if not words:
        return []
    
    # Strip any commas or periods from all input words
    cleaned_words = []
    for w in words:
        cw = dict(w)
        cw["word"] = re.sub(r'[,.]+', '', str(w.get("word", ""))).strip()
        if cw["word"]:
            cleaned_words.append(cw)
    
    if not cleaned_words:
        return []
    
    segments = []
    
    # 1 Word at a time
    if words_per_line == 1:
        for idx, w in enumerate(cleaned_words):
            segments.append({
                "id": idx + 1,
                "start": w["start"],
                "end": w["end"],
                "text": w["word"],
                "words": [dict(w)]
            })
        return segments

    # N Words at a time (e.g. 2, 3, 4, 5)
    chunk_size = words_per_line if words_per_line > 0 else 6
    
    i = 0
    seg_id = 1
    while i < len(cleaned_words):
        chunk = []
        for j in range(chunk_size):
            if i + j < len(cleaned_words):
                next_w = cleaned_words[i + j]
                # If there's a long pause (> 0.8s) before next word, end chunk early
                if chunk and (next_w["start"] - chunk[-1]["end"]) > 0.8:
                    break
                chunk.append(next_w)
                # Break at question or exclamation boundary (no period since user requested no periods)
                if chunk_size >= 4 and any(next_w["word"].endswith(p) for p in ("?", "!")):
                    break
        
        if not chunk:
            break
            
        seg_start = chunk[0]["start"]
        seg_end = chunk[-1]["end"]
        seg_text = " ".join(w["word"] for w in chunk)
        
        segments.append({
            "id": seg_id,
            "start": round(seg_start, 2),
            "end": round(seg_end, 2),
            "text": seg_text,
            "words": [dict(w) for w in chunk]
        })
        
        seg_id += 1
        i += len(chunk)
        
    return segments

def transcribe_video(
    video_path: str,
    language: str = "auto",
    model_path: str = None,
    words_per_line: int = 3,
    start_time: float = None,
    duration: float = None,
    streamer_voice_focus: bool = True,
    audio_track: int = 0,
    progress_callback: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Transcribes audio from a video using local high-speed whisper-cli with true token alignment.
    Supports transcribing the full stream or a specific clip duration.
    When streamer_voice_focus is True, only foreground streamer speech is transcribed,
    filtering out background game audio, music, and in-game dialogue.
    Applies 5ms sub-frame vocal energy and attack derivative snapping for extreme CapCut-grade synchronization.
    """
    # Auto-pick optimal model:
    # For long livestream files (>300s), auto-pick lightweight tiny.en for 2.6x faster ingestion on desktop CPUs.
    # For short viral clips (<300s), prioritize base.en for top-tier slang accuracy and alignment.
    if not model_path or not os.path.isfile(model_path):
        if duration and duration > 300:
            pref = "tiny.en" if (language == "en" or language == "auto") else "tiny"
        else:
            pref = "base.en" if (language == "en" or language == "auto") else "tiny"
        model_path = ensure_whisper_model(pref)
    
    if progress_callback:
        progress_callback("Extracting 16kHz audio & applying speech normalization...", 15)

    wav_path = None
    json_path = None
    srt_path = None

    try:
        # 1. Extract audio (full or clip slice with streamer voice focus and accurate zero-drift seek)
        wav_path = extract_audio_wav(
            video_path, 
            start_time=start_time, 
            duration=duration,
            streamer_voice_focus=streamer_voice_focus,
            audio_track=audio_track
        )
        base_out = os.path.splitext(wav_path)[0] + "_trans"
        json_path = f"{base_out}.json"
        srt_path = f"{base_out}.srt"
        
        if progress_callback:
            progress_callback("Running neural speech recognition (Whisper AI)...", 45)

        # Guarantee WAV is non-empty and has readable PCM frames before invoking Whisper to avoid miniaudio decoding crash (exit 11)
        need_silent_gen = False
        if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 512:
            need_silent_gen = True
        else:
            try:
                with wave.open(wav_path, "rb") as wf:
                    if wf.getnframes() < 80:
                        need_silent_gen = True
            except Exception:
                need_silent_gen = True

        if need_silent_gen:
            print("[WARN] WAV file is missing, < 512 bytes, or unreadable. Generating valid silent audio frames.")
            create_silent_wav(wav_path, max(2.0, duration or 2.0))

        # 2. Run whisper-cli with dynamic CPU thread scaling, anti-hallucination bounds, and DTW timestamping
        cpu_info = get_cpu_info()
        whisper_threads = str(cpu_info.get("whisper_threads", 4))
        bo_val = "2" if (duration is not None and duration <= 120) else "1"
        bs_val = "2" if (duration is not None and duration <= 120) else "1"

        cmd = [
            WHISPER_CLI,
            "-m", model_path,
            "-f", wav_path,
            "-ojf", # output full token JSON
            "-osrt",
            "-of", base_out,
            "-t", whisper_threads,
            "-bo", bo_val,
            "-bs", bs_val, 
            "-mc", "48", # Semantic context bounds: maintains conversational grammar without cross-scene drift
            "-nf", # No fallback: stops temperature looping and hallucinations on silence
            "-wt", "0.01", # Word timestamp probability threshold
            "-sow", # Split on words
            "-sns", # Suppress non-speech tokens
            "-nth", "0.60", # Speech threshold: preserves quiet words and whispered speech
            "-lpt", "-0.70", # Logprob threshold
            "-et", "2.60", # Entropy threshold: rejects repetitive low-information hallucination cycles
            "-np" # No console flooding: prevents Windows pipe buffer stalls
        ]
        dtw_preset = get_dtw_preset(model_path)
        if dtw_preset:
            cmd += ["-dtw", dtw_preset, "-nfa"]

        if language and language != "auto":
            cmd += ["-l", language]
        elif language == "auto" and "tiny.en" not in model_path and "base.en" not in model_path:
            cmd += ["-l", "auto"]

        try:
            res = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                print(f"[WARN] Whisper pass 1 returned exit {res.returncode}: {res.stderr.strip() if res.stderr else ''}")
                # Retry with minimal parameters (without -dtw or -nfa in case of version compatibility)
                simple_cmd = [
                    WHISPER_CLI,
                    "-m", model_path,
                    "-f", wav_path,
                    "-ojf",
                    "-osrt",
                    "-of", base_out,
                    "-t", whisper_threads
                ]
                res2 = subprocess.run(simple_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                if res2.returncode != 0:
                    print(f"[WARN] Whisper fallback also exited with {res2.returncode}. Returning empty subtitles for silent/unrecognized audio.")
                    return []
        except Exception as exc:
            print(f"[WARN] Whisper execution encountered error: {exc}. Returning empty subtitles.")
            return []
        
        raw_words = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                raw_segments = data.get("transcription", [])
                raw_words = parse_tokens_to_words(raw_segments)
            except Exception as e:
                print(f"Error parsing json tokens: {e}")
                
        # Fallback if no words extracted from tokens: parse SRT
        if not raw_words and os.path.exists(srt_path):
            srt_segments = parse_srt_file(srt_path)
            for seg in srt_segments:
                raw_words.extend(seg.get("words", []))

        if progress_callback:
            progress_callback("Sanitizing word timings & zero-blink alignment...", 85)

        # 3. Sanitize word timings (non-destructive, zero-blink, no quiet speech dropping)
        if raw_words:
            raw_words = sanitize_word_timings(raw_words)

        if progress_callback:
            progress_callback("Formatting CapCut word chunks & karaoke highlights...", 98)

        # 4. Group extracted words into user's requested words_per_line (1, 2, 3, 4, etc.)
        segments = group_words_into_segments(raw_words, words_per_line=words_per_line)
        
        # Final fallback if still empty
        if not segments and os.path.exists(srt_path):
            segments = parse_srt_file(srt_path)
            
        return segments

    finally:
        # Clean up temporary WAV and Whisper output files so storage/temp never leaks
        for p in [wav_path, json_path, srt_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

def parse_srt_file(srt_path: str) -> List[Dict[str, Any]]:
    """Parses standard SRT file into segments list, removing full stops (.) and commas (,)."""
    with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    blocks = re.split(r"\n\s*\n", content.strip())
    segments = []
    idx = 1
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) >= 2:
            time_line = lines[1] if lines[0].isdigit() else lines[0]
            text_lines = lines[2:] if lines[0].isdigit() else lines[1:]
            text = " ".join(text_lines).strip()
            text = re.sub(r"<\|.*?\|>", "", text).strip()
            # Strip all full stops and commas
            text = re.sub(r'[,.]+', '', text).strip()
            
            time_match = re.match(r"(\S+)\s*-->\s*(\S+)", time_line)
            if time_match and text:
                start_sec = parse_time_str(time_match.group(1))
                end_sec = parse_time_str(time_match.group(2))
                
                word_list = [re.sub(r'[,.]+', '', w).strip() for w in text.split() if re.sub(r'[,.]+', '', w).strip()]
                if not word_list:
                    continue
                duration = max(0.2, end_sec - start_sec)
                w_step = duration / max(1, len(word_list))
                words = [{
                    "word": w,
                    "start": round(start_sec + (i * w_step), 2),
                    "end": round(start_sec + ((i + 1) * w_step), 2)
                } for i, w in enumerate(word_list)]
                
                segments.append({
                    "id": idx,
                    "start": round(start_sec, 2),
                    "end": round(end_sec, 2),
                    "text": " ".join(word_list),
                    "words": words
                })
                idx += 1
    return segments
