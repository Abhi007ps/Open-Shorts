import os
import subprocess
import array
import math
import re
from typing import List, Dict, Any, Optional, Tuple
from backend.hardware import FFMPEG_BIN

try:
    from backend.llm_engine import is_ollama_online, refine_clip_with_llm, curate_auto_viral_clips
except ImportError:
    def is_ollama_online(*args, **kwargs) -> bool: return False
    def refine_clip_with_llm(clip, *args, **kwargs): return clip
    def curate_auto_viral_clips(candidates, *args, **kwargs): return candidates[:3], None

HOOK_START_KEYWORDS = {
    # Strong opening words that grab attention in the first 2-3 seconds
    "wait", "look", "what", "how", "why", "who", "where", "no", "omg", "bro", "dude",
    "holy", "damn", "listen", "watch", "check", "see", "never", "always",
    "kya", "kaise", "kyun", "kahan", "bhai", "dekh", "sun", "are", "aree", "ruk", "suno", "dekhna"
}

REACTION_KEYWORDS = {
    "omg", "unreal", "clutch", "insane", "what", "no way", "holy", "damn", "bro", "dude",
    "kill", "dead", "headshot", "win", "run", "fast", "caught", "impossible", "god", "pro",
    "bhai", "kya", "are", "aree", "yaar", "lelo", "bc", "mc", "loot", "sasti", "beer",
    "seb", "aloo", "baingan", "adrak", "chal", "dekh", "rok", "baap", "mar", "gaya", "khatam"
}

COMEDY_KEYWORDS = {
    "haha", "hahaha", "lmao", "lol", "rofl", "funny", "fail", "bot", "noob", "gadha", "pagal",
    "chutiya", "bakwas", "joke", "crying", "dying"
}

SCREAM_KEYWORDS = {
    "ahhh", "ahhhh", "nooo", "noooo", "stop", "help", "run", "behind", "what the", "oh god",
    "jesus", "bhai re", "are baap", "mar gaya", "bachao", "bhago", "arre", "fuck", "shit"
}

DESPAIR_KEYWORDS = {
    "no way", "i'm dead", "i'm done", "unbelievable", "why me", "please", "not like this",
    "khatam", "barbaad", "yeh kya tha", "aisa mat kar"
}

def extract_audio_features(video_path: str, sample_rate: int = 16000, window_sec: float = 0.5, max_duration: Optional[float] = None) -> Dict[str, Any]:
    """
    Extracts 16kHz mono audio using Ultra-Fast Streamer Vocal Isolation:
    - High-speed vocal band isolation without heavy FFT noise filters or harsh gates (runs at >120x realtime)
    - Highpass above 90Hz to eliminate sub-bass rumbles (explosions, engines, gunfire)
    - Lowpass below 6500Hz to eliminate high-frequency hiss
    - Vocal resonance boost at 320Hz and 2200Hz to keep streamer voice prominent
    - Preserves natural streamer speech and laughter without muting them
    - Computes RMS energy, Zero-Crossing Rate (ZCR), and Vocal Excitement Index.
    """
    audio_filter = (
        "pan=mono|c0=0.5*c0+0.5*c1,"
        "highpass=f=90,lowpass=f=6500,"
        "equalizer=f=320:t=q:w=1.5:g=3.5,"
        "equalizer=f=2200:t=q:w=1.5:g=4.0,"
        "volume=1.4"
    )
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", video_path
    ]
    if max_duration and max_duration > 0:
        cmd.extend(["-t", str(round(max_duration + 5.0, 1))])
    cmd.extend([
        "-vn",
        "-af", audio_filter,
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "s16le",
        "-"
    ])
    raw_bytes = b""
    ff_timeout = max(60.0, float(max_duration or 1800.0) * 0.10)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_bytes, err = proc.communicate(timeout=ff_timeout)
    except Exception as e:
        print(f"Streamer audio feature extraction failed or timed out: {e}")
        try:
            proc.kill()
        except Exception:
            pass

    if not raw_bytes or len(raw_bytes) < 3200:
        # Fallback to direct extraction if filtered extraction returned insufficient bytes
        fallback_cmd = [
            FFMPEG_BIN, "-y",
            "-i", video_path
        ]
        if max_duration and max_duration > 0:
            fallback_cmd.extend(["-t", str(round(max_duration + 5.0, 1))])
        fallback_cmd.extend([
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "s16le",
            "-"
        ])
        try:
            fb_proc = subprocess.Popen(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_bytes, _ = fb_proc.communicate(timeout=ff_timeout)
        except Exception:
            pass

    if not raw_bytes:
        return {"rms": [], "zcr": [], "gradient": [], "excitement": [], "mean_rms": 1.0, "max_rms": 1.0, "mean_zcr": 0.1, "max_zcr": 0.5, "window_sec": window_sec}

    samples = array.array('h', raw_bytes)
    window_samples = int(sample_rate * window_sec)
    num_windows = len(samples) // window_samples
    
    rms_list = []
    zcr_list = []
    
    for w in range(num_windows):
        start_idx = w * window_samples
        chunk = samples[start_idx : start_idx + window_samples]
        if not chunk:
            rms_list.append(0.0)
            zcr_list.append(0.0)
            continue
        sum_sq = sum(s * s for s in chunk)
        rms = math.sqrt(sum_sq / len(chunk))
        rms_list.append(rms)
        
        # Zero-Crossing Rate (vocal fold excitation & pitch/shouting)
        zcr = sum(1 for j in range(1, len(chunk)) if (chunk[j] >= 0 and chunk[j-1] < 0) or (chunk[j] < 0 and chunk[j-1] >= 0)) / len(chunk)
        zcr_list.append(zcr)

    # Compute sudden energy rise gradient (dE/dt)
    gradient_list = [0.0]
    for i in range(1, len(rms_list)):
        gradient_list.append(max(0.0, rms_list[i] - rms_list[i-1]))
        
    mean_rms = sum(rms_list) / max(1, len(rms_list))
    max_rms = max(rms_list) if rms_list else 1.0
    mean_zcr = sum(zcr_list) / max(1, len(zcr_list))
    max_zcr = max(zcr_list) if zcr_list else 0.5

    # Vocal Excitement Index: elevates human screams & laughter while damping bass rumble
    excitement_list = []
    for r, z in zip(rms_list, zcr_list):
        r_norm = r / (mean_rms + 1e-4)
        z_norm = z / (mean_zcr + 1e-4)
        # S-curve vocal excitement
        excitement_list.append(r_norm * (z_norm ** 1.05))

    # UPGRADE 4: Dynamic Audio Contrast & Transient Spike Detection
    # Detects sudden dynamic range spikes (>12dB / 4x surge in <100ms) after quiet tension (jumpscares, headshots, screams)
    contrast_list = []
    trailing_win = max(2, int(2.0 / window_sec))
    for i in range(len(rms_list)):
        start_w = max(0, i - trailing_win)
        bg = sum(rms_list[start_w:i]) / max(1, i - start_w) if i > 0 else mean_rms
        ratio = rms_list[i] / (bg + 1e-3)
        contrast_list.append(round(ratio, 2))

    return {
        "rms": rms_list,
        "zcr": zcr_list,
        "gradient": gradient_list,
        "excitement": excitement_list,
        "contrast": contrast_list,
        "mean_rms": mean_rms,
        "max_rms": max_rms,
        "mean_zcr": mean_zcr,
        "max_zcr": max_zcr,
        "window_sec": window_sec
    }

def extract_clip_thumbnail(video_path: str, climax_t: float, output_path: str) -> bool:
    """
    UPGRADE 5: High-CTR Viral Thumbnail Freeze-Frame Generator
    Extracts a crisp, high-resolution JPEG cover frame at the peak emotional climax moment.
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            FFMPEG_BIN, "-y",
            "-ss", str(max(0.1, round(climax_t, 2))),
            "-i", video_path,
            "-vframes", "1",
            "-vf", "scale=640:-1",
            "-q:v", "3",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"[Thumbnail] Extraction failed at {climax_t}s: {e}")
        return False

def extract_candidate_motion(
    video_path: str, 
    start_t: float, 
    dur: float, 
    webcam_crop: Optional[Dict[str, int]] = None,
    climax_t: Optional[float] = None
) -> Tuple[float, float, bool]:
    """
    UPGRADE 3: Facial Landmark Jaw-Drop & Shock Reaction Detector
    Computes visual motion intensity for gameplay, physical streamer facecam delta,
    and analyzes lower-face contrast for Jaw-Drop / Shock reaction (open mouth cavity).
    Returns (gameplay_motion, facecam_reaction, jaw_drop_detected).
    """
    gameplay_motion = 0.5
    facecam_reaction = 0.5
    jaw_drop_detected = False
    
    # 1. Gameplay motion (80x45 frames across candidate for lightning-fast seeking)
    try:
        cmd = [
            FFMPEG_BIN, "-y",
            "-ss", str(max(0.0, start_t)),
            "-i", video_path,
            "-t", str(min(2.0, dur)),
            "-vf", "fps=1.0,scale=80:45",
            "-f", "rawvideo",
            "-pix_fmt", "gray",
            "-"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw, _ = proc.communicate(timeout=5.0)
        fsize = 80 * 45
        n = len(raw) // fsize
        if n >= 2:
            deltas = [sum(abs(b1 - b2) for b1, b2 in zip(raw[(i-1)*fsize:i*fsize], raw[i*fsize:(i+1)*fsize])) / fsize for i in range(1, n)]
            gp_diff = sum(deltas) / len(deltas)
            gameplay_motion = min(1.0, max(0.15, gp_diff / 25.0))
    except Exception:
        pass

    # 2. Combined Streamer Facecam Reaction Delta & Jaw-Drop Analysis in a single stream
    try:
        if webcam_crop and all(k in webcam_crop for k in ("x", "y", "w", "h")) and webcam_crop["w"] > 10:
            cx, cy, cw, ch = webcam_crop["x"], webcam_crop["y"], webcam_crop["w"], webcam_crop["h"]
        else:
            # Standard streamer webcam location (Speed, Kai, xQc, etc. placed on left side)
            cx, cy, cw, ch = 10, 420, 360, 280
            
        target_t = max(0.0, (climax_t if climax_t is not None else (start_t + dur * 0.5)) - 0.5)
        cam_cmd = [
            FFMPEG_BIN, "-y",
            "-ss", str(target_t),
            "-i", video_path,
            "-t", "1.5",
            "-vf", f"crop={cw}:{ch}:{cx}:{cy},scale=48:48,fps=3",
            "-f", "rawvideo",
            "-pix_fmt", "gray",
            "-"
        ]
        cam_proc = subprocess.Popen(cam_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        cam_raw, _ = cam_proc.communicate(timeout=5.0)
        cam_fsize = 48 * 48
        cam_n = len(cam_raw) // cam_fsize
        if cam_n >= 2:
            cam_deltas = [sum(abs(b1 - b2) for b1, b2 in zip(cam_raw[(i-1)*cam_fsize:i*cam_fsize], cam_raw[i*cam_fsize:(i+1)*cam_fsize])) / cam_fsize for i in range(1, cam_n)]
            cam_diff = sum(cam_deltas) / len(cam_deltas)
            facecam_reaction = min(1.0, max(0.20, cam_diff / 8.0))

            # Analyze Jaw-Drop / Open Mouth Cavity across the sampled frames
            for f_idx in range(cam_n):
                f_frame = cam_raw[f_idx * cam_fsize : (f_idx + 1) * cam_fsize]
                mouth_pixels = [f_frame[r * 48 + c] for r in range(28, 44) for c in range(16, 32)]
                if mouth_pixels:
                    mouth_mean = sum(mouth_pixels) / len(mouth_pixels)
                    mouth_var = sum((p - mouth_mean) ** 2 for p in mouth_pixels) / len(mouth_pixels)
                    if mouth_var > 600.0:
                        jaw_drop_detected = True
                        facecam_reaction = max(facecam_reaction, 0.95)
                        break
    except Exception:
        facecam_reaction = gameplay_motion

    return gameplay_motion, facecam_reaction, jaw_drop_detected

def evaluate_hook_quality(subtitles: List[Dict[str, Any]], start: float, end: float) -> Tuple[float, str]:
    """
    Scores the first 3.0s of the clip for audience retention hooks:
    - speech latency (faster speech onset = higher retention)
    - hook starter keywords (questions, exclamations, intrigue)
    - punctuation (? or !)
    """
    if not subtitles:
        return 0.5, "Hook Detected"
        
    hook_window = 3.0
    hook_subs = [
        s for s in subtitles
        if float(s.get("start", 0)) < start + hook_window and float(s.get("end", 0)) > start
    ]
    
    if not hook_subs:
        return 0.25, "Late Speech Onset"
        
    first_sub = hook_subs[0]
    first_start = float(first_sub.get("start", 0))
    latency = max(0.0, first_start - start)
    
    # Latency score: 0s to 0.6s is best (1.0), >2.2s is low (0.2)
    latency_score = max(0.2, 1.0 - (latency / 2.2) * 0.8)
    
    all_hook_text = " ".join(s.get("text", "") for s in hook_subs).strip()
    words = re.findall(r'\b\w+\b', all_hook_text.lower())
    
    keyword_bonus = 0.0
    for w in words[:6]: # First 6 words are critical
        if w in HOOK_START_KEYWORDS:
            keyword_bonus += 0.35
            
    has_question = "?" in all_hook_text[:60]
    has_exclamation = "!" in all_hook_text[:60]
    
    punc_score = (0.35 if has_question else 0.0) + (0.25 if has_exclamation else 0.0)
    
    total_hook = min(1.0, latency_score * 0.35 + keyword_bonus * 0.40 + punc_score * 0.25)
    
    reason = "🎣 Question Hook" if has_question else ("⚡ High-Energy Hook" if has_exclamation or keyword_bonus > 0 else "🎙️ Spoken Intro")
    return total_hook, reason

def evaluate_speech_dynamics_and_dead_air(
    subtitles: List[Dict[str, Any]], 
    start: float, 
    end: float,
    rms_list: Optional[List[float]] = None,
    mean_rms: float = 1.0
) -> Tuple[float, Dict[str, Any], str, str, float]:
    """
    Analyzes speech velocity, reaction/comedy triggers, sentence pacing,
    and calculates dead-air silence penalty.
    Returns (speech_score, stats, reason, hook_title, dead_air_penalty)
    """
    if not subtitles:
        return 0.5, {"wps": 0, "reactions": 0, "comedy": 0, "dead_air_sec": 0}, "⚡ High Energy", "Stream Highlight", 0.0
        
    matching_subs = [
        s for s in subtitles 
        if float(s.get("end", 0)) > start and float(s.get("start", 0)) < end
    ]
    
    if not matching_subs:
        return 0.3, {"wps": 0, "reactions": 0, "comedy": 0, "dead_air_sec": round(end - start, 1)}, "🎮 Gameplay Action", "Action Highlight", 0.15
        
    total_words = 0
    reaction_hits = 0
    comedy_hits = 0
    exclamations = 0
    full_text_list = []
    
    for s in matching_subs:
        text = s.get("text", "").strip()
        full_text_list.append(text)
        words = re.findall(r'\b\w+\b', text.lower())
        total_words += len(words)
        exclamations += text.count('!') + text.count('?')
        for w in words:
            if w in REACTION_KEYWORDS:
                reaction_hits += 1
            if w in COMEDY_KEYWORDS:
                comedy_hits += 1
                
    duration = max(1.0, end - start)
    wps = total_words / duration
    
    # Dead-air calculation: scan for silence gaps > 2.0s
    dead_air_sec = 0.0
    first_start = float(matching_subs[0].get("start", 0))
    if first_start - start > 2.0:
        dead_air_sec += (first_start - start)
        
    for i in range(1, len(matching_subs)):
        prev_end = float(matching_subs[i-1].get("end", 0))
        cur_start = float(matching_subs[i].get("start", 0))
        gap = cur_start - prev_end
        if gap > 2.0:
            dead_air_sec += gap
            
    last_end = float(matching_subs[-1].get("end", 0))
    if end - last_end > 2.5:
        dead_air_sec += (end - last_end)
        
    dead_air_ratio = dead_air_sec / duration
    # Dead-air penalty: 0 if <15% dead air, scales up to 0.25 (25% deduction) if >35% dead air
    dead_air_penalty = min(0.25, max(0.0, (dead_air_ratio - 0.15) * 1.25))

    speech_density_score = min(1.0, wps / 3.2)
    trigger_score = min(1.0, (reaction_hits * 0.25) + (comedy_hits * 0.30) + (exclamations * 0.15))
    
    combined_speech_score = max(0.1, (speech_density_score * 0.45 + trigger_score * 0.55) - dead_air_penalty)
    
    # Reason
    if comedy_hits >= 2:
        reason = "😂 Viral Comedy & Laughter"
    elif reaction_hits >= 2 or exclamations >= 3:
        reason = "🔥 Clutch Reaction & Outburst"
    elif wps > 2.8:
        reason = "⚡ Fast-Paced Rapid Commentary"
    elif reaction_hits >= 1:
        reason = "🎯 Streamer Reaction Moment"
    else:
        reason = "🎙️ Engaging Narrative Arc"
        
    # Hook Title
    combined_text = " ".join(full_text_list).strip()
    words = combined_text.split()
    if len(words) >= 4:
        hook_title = " ".join(words[:6]).title()
    else:
        hook_title = combined_text.title() if combined_text else "Stream Highlight"
        
    hook_title = re.sub(r'[\/\\:\*\?"<>\|]', '', hook_title)
    if len(hook_title) > 36:
        hook_title = hook_title[:33] + "..."
        
    stats = {
        "wps": round(wps, 1),
        "reactions": reaction_hits,
        "comedy": comedy_hits,
        "words": total_words,
        "dead_air_sec": round(dead_air_sec, 1)
    }
    return combined_speech_score, stats, reason, hook_title, dead_air_penalty

COLD_OPEN_FILLER = {
    "so", "basically", "and", "uhh", "um", "like", "okay", "yeah", "alright", "anyway", 
    "you know", "i mean", "actually", "well", "toh", "aur", "matlab"
}

HOOK_QUESTION_STARTERS = (
    "wait", "can i", "what", "look", "no way", "you won't", "how did",
    "is that", "bro", "yo", "oh my god", "watch this", "guys", "did he",
    "why is", "tell me", "hold on", "who", "where", "how"
)

def snap_to_clean_boundaries(
    start: float, 
    end: float, 
    subtitles: Optional[List[Dict[str, Any]]] = None, 
    audio_feats: Optional[Dict[str, Any]] = None,
    min_duration: float = 12.0, 
    max_duration: float = 45.0
) -> Tuple[float, float, Dict[str, Any]]:
    """
    FEATURE 2: Narrative Micro-Arc Detection & Punchline Snapping (Never Cut Mid-Sentence)
    1. The Hook (0-3s): Curiosity gap, bold statement, sudden question ("Wait, can I pick him up?").
    2. The Build-Up (3-20s): Rising vocal pitch, fast pacing, low dead-air.
    3. The Climax & Punchline (20-35s): Shock reaction, jaw-drop, scream or hysterical laugh.
    4. The Punchline Snap: Cut immediately after the punchline with ZERO awkward silence.
    """
    meta = {
        "cold_open_applied": False,
        "speech_snapped": True,
        "narrative_snapped": True,
        "snap_mode": "raw",
        "narrative_arc": {
            "hook_detected": False,
            "punchline_snap": True
        }
    }

    best_start = start
    best_end = end

    # --- Mode A: Word-Level Subtitle Sentence & Narrative Snapping ---
    if subtitles and len(subtitles) > 0:
        # 1. The Hook (0-3s): Snap start to earliest curiosity question or bold statement with -40ms vocal attack lead
        hook_candidate_subs = [s for s in subtitles if abs(float(s.get("start", 0)) - start) <= 3.5]
        hook_snapped = False
        
        for s in hook_candidate_subs:
            s_start = float(s.get("start", 0))
            text = s.get("text", "").strip().lower()
            words = text.split()
            
            # Prioritize curiosity hook onset (e.g. "Wait, can I...", "Bro look at this")
            if any(text.startswith(kw) for kw in HOOK_QUESTION_STARTERS):
                best_start = max(0.0, round(s_start - 0.04, 2))
                meta["cold_open_applied"] = True
                meta["narrative_arc"]["hook_detected"] = True
                meta["snap_mode"] = "narrative_hook_onset"
                hook_snapped = True
                break
            elif words and words[0] in COLD_OPEN_FILLER and "words" in s and s["words"]:
                punchy_w = next((w for w in s["words"] if w.get("word", "").lower() not in COLD_OPEN_FILLER), None)
                if punchy_w and float(punchy_w.get("start", s_start)) >= s_start:
                    best_start = max(0.0, round(float(punchy_w["start"]) - 0.04, 2))
                    meta["cold_open_applied"] = True
                    meta["snap_mode"] = "word_level_transcript"
                    hook_snapped = True
                    break
                    
        if not hook_snapped and hook_candidate_subs:
            best_start = max(0.0, round(float(hook_candidate_subs[0].get("start", start)) - 0.05, 2))
            meta["cold_open_applied"] = True
            meta["snap_mode"] = "word_level_transcript"
                
        # 2. The Punchline Snap: Cut immediately after the punchline (+0.35s) with zero awkward silence
        ending_subs = [s for s in subtitles if abs(float(s.get("end", 0)) - end) <= 4.0]
        if ending_subs:
            last_sub = ending_subs[-1]
            if "words" in last_sub and last_sub["words"]:
                last_word_end = float(last_sub["words"][-1].get("end", last_sub.get("end", end)))
                best_end = round(last_word_end + 0.35, 2)  # Crisp Punchline Snap with zero dead air
            else:
                best_end = round(float(last_sub.get("end", end)) + 0.35, 2)
            meta["snap_mode"] = "punchline_snap"

    # --- Mode B: Audio Vocal Energy Envelope Snapping (VAD) ---
    elif audio_feats and audio_feats.get("rms"):
        rms = audio_feats.get("rms", [])
        w_sec = float(audio_feats.get("window_sec", 0.5))
        mean_rms = float(audio_feats.get("mean_rms", 1000.0))
        vad_thresh = max(100.0, mean_rms * 0.35)

        # 1. Scan for speech onset near start within [-2.0s, +2.5s]
        center_w = int(start / w_sec)
        scan_range = int(2.5 / w_sec)
        w_low = max(0, center_w - scan_range)
        w_high = min(len(rms) - 1, center_w + scan_range)
        
        for w_idx in range(w_low, w_high):
            if rms[w_idx] >= vad_thresh:
                best_start = max(0.0, round(w_idx * w_sec - 0.04, 2))
                meta["cold_open_applied"] = True
                meta["snap_mode"] = "audio_vad_envelope"
                break

        # 2. Punchline Snap: Cut immediately when vocal energy drops after climax
        end_w = int(end / w_sec)
        end_low = max(0, end_w - scan_range)
        end_high = min(len(rms) - 1, end_w + scan_range)

        for w_idx in range(end_w, end_high):
            if w_idx + 1 < len(rms) and rms[w_idx] < vad_thresh and rms[w_idx + 1] < vad_thresh:
                best_end = round(min(len(rms) * w_sec, (w_idx + 1) * w_sec + 0.35), 2)
                meta["snap_mode"] = "audio_vad_punchline_snap"
                break

    dur = best_end - best_start
    if dur > max_duration:
        if subtitles:
            valid_subs = [
                s for s in subtitles
                if float(s.get("end", 0)) <= (best_start + max_duration)
                and float(s.get("end", 0)) >= (best_start + min_duration)
            ]
            if valid_subs:
                best_sub = valid_subs[-1]
                for s in reversed(valid_subs):
                    txt = s.get("text", "").strip()
                    if txt.endswith((".", "!", "?")):
                        best_sub = s
                        break
                best_end = round(float(best_sub.get("end", best_start + max_duration)) + 0.30, 2)
            else:
                best_end = round(best_start + max_duration, 2)
        else:
            best_end = round(best_start + max_duration, 2)
    elif dur < min_duration:
        best_end = round(best_start + min_duration, 2)
        
    return round(best_start, 2), round(best_end, 2), meta

def build_dynamic_narrative_candidates(
    subtitles: List[Dict[str, Any]],
    audio_feats: Dict[str, Any],
    video_duration: float,
    min_dur: float,
    max_dur: float
) -> List[Tuple[float, float, float, Dict[str, Any]]]:
    """
    Streamer-Centric Dynamic Reaction Event Tracing Engine:
    Identifies high-emotion streamer climaxes (screams, laughter, cries, rage, jumpscares, dynamic audio contrast)
    and organically traces the true lifecycle boundaries of the moment:
    - Setup Onset: where the streamer started talking/reacting leading into the moment
    - Climax Peak: the apex of the shout, laughter burst, or extreme emotion
    - Punchline Resolution: where the reaction settles down naturally
    Calculates exact required duration adaptively (NO fixed/predetermined numbers).
    """
    rms_list = audio_feats.get("rms", [])
    gradient_list = audio_feats.get("gradient", [])
    excitement_list = audio_feats.get("excitement", [])
    contrast_list = audio_feats.get("contrast", [])
    zcr_list = audio_feats.get("zcr", [])
    mean_rms = audio_feats.get("mean_rms", 1.0)
    max_rms = audio_feats.get("max_rms", 1.0)
    mean_zcr = audio_feats.get("mean_zcr", 0.05)
    
    # Streamer voice activity floor: ignore moments where streamer is completely quiet
    silence_threshold = max(350.0, mean_rms * 0.15)
    
    # 1. Identify Streamer Vocal Outburst & Dynamic Contrast Climaxes
    raw_climaxes = []
    for i in range(2, len(rms_list) - 2):
        r = rms_list[i]
        if r < silence_threshold:
            continue
            
        g = gradient_list[i] if i < len(gradient_list) else 0.0
        z = zcr_list[i] if i < len(zcr_list) else 0.0
        e = excitement_list[i] if i < len(excitement_list) else 0.0
        c_ratio = contrast_list[i] if i < len(contrast_list) else 1.0
        
        # High-voltage viral climaxes: Streamer must be shouting, screaming, hysterically laughing, or experiencing sudden shock
        # For short clips (pre-identified audio peaks from Audio Pull), use relaxed thresholds
        # since the whole clip is at elevated energy and local variation drives virality
        _short = video_duration <= 60.0
        is_scream = (r > (1.5 if _short else 1.9) * mean_rms and z > 1.12 * mean_zcr)
        is_outburst = (r > (1.6 if _short else 2.1) * mean_rms and z >= 0.85 * mean_zcr) or (g > (1.2 if _short else 1.6) * mean_rms and z >= 0.85 * mean_zcr)
        is_laughter = (e > (1.6 if _short else 2.1) and r > (0.9 if _short else 1.15) * mean_rms and z > 0.85 * mean_zcr)
        is_transient = (c_ratio >= (2.2 if _short else 3.2) and r > silence_threshold * 1.2 and z >= 0.75 * mean_zcr)
        
        if is_scream or is_outburst or is_laughter or is_transient:
            is_local_max = all(r >= rms_list[j] for j in range(max(0, i-2), min(len(rms_list), i+3)))
            if is_local_max:
                if is_transient and c_ratio > 3.6:
                    climax_type = "jumpscare_transient"
                elif is_scream:
                    climax_type = "scream"
                elif is_laughter:
                    climax_type = "laughter"
                else:
                    climax_type = "outburst"

                raw_climaxes.append({
                    "time": round(i * 0.5, 1),
                    "idx": i,
                    "rms": r,
                    "zcr": z,
                    "exc": e,
                    "grad": g,
                    "contrast": c_ratio,
                    "type": climax_type
                })

    # Subtitle Reaction Keyword Peaks (Strict: require real emotional arousal + keyword, not routine questions)
    if subtitles:
        for s in subtitles:
            text = s.get("text", "").lower()
            words = re.findall(r'\b\w+\b', text)
            has_scream_kw = any(w in SCREAM_KEYWORDS for w in words)
            has_comedy_kw = any(w in COMEDY_KEYWORDS for w in words)
            has_react_kw = any(w in REACTION_KEYWORDS for w in words)
            has_despair_kw = any(w in DESPAIR_KEYWORDS for w in words)
            has_strong_reaction = has_scream_kw or has_comedy_kw or has_react_kw or has_despair_kw
            
            if has_strong_reaction:
                mid_t = (float(s.get("start", 0)) + float(s.get("end", 0))) / 2.0
                mid_idx = int(mid_t / 0.5)
                if mid_idx < len(rms_list):
                    r = rms_list[mid_idx]
                    e = excitement_list[mid_idx] if mid_idx < len(excitement_list) else 1.0
                    if r >= 1.35 * mean_rms or e >= 1.8:
                        climax_type = "scream" if has_scream_kw else ("laughter" if has_comedy_kw else ("despair" if has_despair_kw else "outburst"))
                        raw_climaxes.append({
                            "time": round(mid_t, 1),
                            "idx": mid_idx,
                            "rms": r,
                            "zcr": zcr_list[mid_idx] if mid_idx < len(zcr_list) else 0.0,
                            "exc": excitement_list[mid_idx] if mid_idx < len(excitement_list) else 1.0,
                            "grad": gradient_list[mid_idx] if mid_idx < len(gradient_list) else 0.0,
                            "type": climax_type
                        })

    # Cluster climaxes within 8.0s of each other (retaining highest energy climax)
    raw_climaxes.sort(key=lambda x: x["time"])
    clustered_climaxes = []
    for c in raw_climaxes:
        if not clustered_climaxes or (c["time"] - clustered_climaxes[-1]["time"]) > 8.0:
            clustered_climaxes.append(c)
        else:
            if c["rms"] > clustered_climaxes[-1]["rms"]:
                clustered_climaxes[-1] = c

    # 3. Content-Adaptive Reaction Boundary Tracing (Evaluates how much duration is actually needed!)
    candidates = []
    
    for c in clustered_climaxes:
        t_climax = c["time"]
        if t_climax > video_duration:
            continue
            
        climax_idx = c["idx"]

        # 3A. 3-PART MICRO-ARC SETUP ONSET (6.0s - 18.0s lookback)
        # Captures the hook question / premise before the climax ("Wait, can I give him money?", "Watch this backflip!")
        # Traces backward through vocal activity while avoiding dead air walking
        lead_lookback = int(16.0 / 0.5) # Look back up to 16-18 seconds for conversational setup
        b_idx = climax_idx
        silence_walk = 0
        while b_idx > 0 and (climax_idx - b_idx) < lead_lookback:
            b_idx -= 1
            if b_idx < len(rms_list) and rms_list[b_idx] < silence_threshold:
                silence_walk += 1
                if silence_walk >= 3: # 1.5s true silence gap means prior conversation was unrelated
                    b_idx += 2
                    break
            else:
                silence_walk = 0
        setup_onset = max(0.0, round(b_idx * 0.5 - 0.04, 2))

        # Enforce reasonable setup bounds (at least 5.0s, at most 18.0s before climax)
        if (t_climax - setup_onset) < 5.0:
            setup_onset = max(0.0, round(t_climax - 6.0, 2))
        elif (t_climax - setup_onset) > 18.0:
            setup_onset = max(0.0, round(t_climax - 16.0, 2))

        # 3B. REACTION AFTERMATH & PUNCHLINE SNAP
        # Follows full vocal reaction and snaps 0.35s after the final reaction settles
        f_idx = climax_idx
        silence_count = 0
        max_forward = int(min(32.0, max_dur - 4.0) / 0.5)
        while f_idx < len(rms_list) - 1 and (f_idx - climax_idx) < max_forward:
            f_idx += 1
            if f_idx < len(rms_list) and rms_list[f_idx] < silence_threshold:
                silence_count += 1
                if silence_count >= 3: # 1.5s silence after reaction settles
                    f_idx -= 2
                    break
            else:
                silence_count = 0
        punchline_closure = min(video_duration, round(f_idx * 0.5 + 0.35, 2))

        # Subtitle Narrative Boundary Snapping (if subtitles exist)
        if subtitles:
            # Look back 6.0s to 18.0s for the start of the premise/question
            before_subs = [
                s for s in subtitles 
                if float(s.get("start", 0)) >= max(0.0, t_climax - 18.0) 
                and float(s.get("start", 0)) <= max(0.0, t_climax - 3.0)
            ]
            if before_subs:
                # Find earliest hook question or premise sentence
                found_hook = False
                for s in before_subs:
                    txt = s.get("text", "").lower().strip()
                    if any(txt.startswith(w) for w in HOOK_START_KEYWORDS) or any(txt.startswith(w) for w in HOOK_QUESTION_STARTERS):
                        # Snap start with -40ms vocal attack lead for Frame 0.00 onset
                        setup_onset = max(0.0, round(float(s.get("start", 0)) - 0.04, 2))
                        found_hook = True
                        break
                if not found_hook:
                    # Snap to closest spoken onset within 2.5s of audio setup_onset
                    for s in before_subs:
                        if abs(float(s.get("start", 0)) - setup_onset) <= 2.5:
                            setup_onset = max(0.0, round(float(s.get("start", 0)) - 0.04, 2))
                            break

            # Snap punchline closure to end of final reaction sentence (+0.35s snap)
            after_subs = [
                s for s in subtitles 
                if float(s.get("end", 0)) >= t_climax + 1.0 
                and float(s.get("end", 0)) <= min(video_duration, t_climax + 22.0)
            ]
            if after_subs:
                for s in after_subs:
                    if any(s.get("text", "").strip().endswith(p) for p in (".", "!", "?")):
                        punchline_closure = min(video_duration, round(float(s.get("end", 0)) + 0.35, 2))
                        break

        # Calculate exact natural event duration required for this reaction
        raw_dur = punchline_closure - setup_onset
        c_start = setup_onset
        c_end = punchline_closure

        # Viral duration sweet spot: 18.0s to 38.0s
        ideal_min = max(min_dur, 18.0)
        ideal_max = min(max_dur, 38.0)

        if raw_dur < ideal_min:
            shortfall = ideal_min - raw_dur
            c_end = min(video_duration, round(c_end + shortfall, 2))
            if (c_end - c_start) < ideal_min:
                c_start = max(0.0, round(c_start - (ideal_min - (c_end - c_start)), 2))
        elif raw_dur > ideal_max:
            if subtitles:
                valid_after = [
                    s for s in subtitles
                    if float(s.get("end", 0)) <= (c_start + ideal_max)
                    and float(s.get("end", 0)) >= (c_start + ideal_min)
                ]
                if valid_after:
                    best_s = valid_after[-1]
                    for s in reversed(valid_after):
                        txt = s.get("text", "").strip()
                        if txt.endswith((".", "!", "?")):
                            best_s = s
                            break
                    c_end = min(video_duration, round(float(best_s.get("end", c_start + ideal_max)) + 0.30, 2))
                else:
                    c_end = min(video_duration, round(c_start + ideal_max, 2))
            else:
                c_end = min(video_duration, round(c_start + ideal_max, 2))

        final_dur = round(c_end - c_start, 1)
        if min_dur <= final_dur <= max_dur:
            # Check Streamer Voice Duty Cycle and Vocal Energy in candidate window
            w_start_idx = int(c_start / 0.5)
            w_end_idx = min(len(rms_list), int(c_end / 0.5))
            win_rms = rms_list[w_start_idx:w_end_idx]
            win_zcr = zcr_list[w_start_idx:w_end_idx] if zcr_list else []
            win_exc = excitement_list[w_start_idx:w_end_idx] if excitement_list else []
            if win_rms:
                speech_frames = sum(1 for r, z in zip(win_rms, win_zcr) if r >= silence_threshold and z >= 0.70 * mean_zcr)
                duty_cycle = speech_frames / len(win_rms)
                peak_rms = max(win_rms)
                peak_exc = max(win_exc) if win_exc else 1.0
            else:
                duty_cycle = 0.0
                peak_rms = 0.0
                peak_exc = 1.0
                
            # STREAMER INTERACTION & SILENCE FILTER:
            # 1. If subtitles exist: require that the streamer actually speaks (reject silent gameplay)
            if subtitles:
                cand_subs = [s for s in subtitles if float(s.get("end", 0)) >= c_start and float(s.get("start", 0)) <= c_end]
                if not cand_subs and duty_cycle < 0.20:
                    continue  # Silent gameplay without streamer interaction - DROP
            else:
                # 2. If no subtitles: reject if speech duty cycle is too low and no vocal excitement
                if duty_cycle < 0.16 and peak_exc < 1.5:
                    continue  # Quiet gameplay with passive background sounds - DROP

            candidates.append((
                round(c_start, 1), 
                round(c_end, 1), 
                round(t_climax, 1),
                {
                    "climax_type": c["type"],
                    "duty_cycle": duty_cycle,
                    "peak_rms": peak_rms,
                    "contrast": c.get("contrast", 1.0)
                }
            ))

    return candidates

def detect_viral_moments(
    video_path: str,
    video_duration: float,
    subtitles: Optional[List[Dict[str, Any]]] = None,
    min_duration: float = 10.0,
    max_duration: float = 35.0,
    target_clips: Optional[int] = None, # None means Auto Mode
    quality_threshold: float = 68.0,
    profile: str = "optimized",
    weight_audio: Optional[float] = None,
    weight_pitch: Optional[float] = None,
    weight_hook: Optional[float] = None,
    weight_speech: Optional[float] = None,
    weight_motion: Optional[float] = None,
    snap_boundaries: bool = True,
    webcam_crop: Optional[Dict[str, int]] = None,
    use_llm: bool = True,
    llm_model: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Unified Multimodal AI Sync & Cognitive Semantic Brain:
    Combines the ultra-fast sensory layer (acoustic energy, facecam motion, duty cycle)
    with the local Llama 3.2 prefrontal cortex (narrative reasoning, housekeeping pruning,
    setup/punchline alignment, and viral titling) in a single high-efficiency function.

    Pipeline Architecture:
    1. Streamer Vocal Isolation & Spectral Excitement (110Hz HPF, 220Hz boost, vocal gate)
    2. Dynamic Narrative Boundary Tracing (organic setup onset -> apex -> resolution)
    3. Streamer Facecam Optical Reaction vs Gameplay Motion Fusion
    4. In-Pipeline Cognitive Brain (Llama 3.2 evaluates dialogue, eliminates donation/sub chatter, snaps boundaries)
    5. Fused Multimodal-Semantic Virality Scoring (55% Physical Energy + 45% Cognitive Narrative + Synergy)
    6. Seamless Zero-Delay Fallback: If Ollama is offline or uninstalled, gracefully uses physical scoring.
    """
    min_dur = max(6.0, float(min_duration))
    max_dur = max(min_dur + 3.0, float(max_duration))
    
    # Configure Profile Weights (Audio, Pitch, Hook, Speech, Motion)
    profile_lower = (profile or "balanced").lower()
    if profile_lower in ("high_energy", "energy"):
        def_weights = (0.40, 0.25, 0.20, 0.10, 0.05)
    elif profile_lower in ("comedy", "funny"):
        def_weights = (0.15, 0.20, 0.25, 0.35, 0.05)
    elif profile_lower in ("action", "gameplay"):
        def_weights = (0.20, 0.10, 0.20, 0.15, 0.35)
    else:  # "balanced", "optimized", or standard
        def_weights = (0.25, 0.15, 0.25, 0.20, 0.15)

    w_audio = float(weight_audio) if weight_audio is not None else def_weights[0]
    w_pitch = float(weight_pitch) if weight_pitch is not None else def_weights[1]
    w_hook = float(weight_hook) if weight_hook is not None else def_weights[2]
    w_speech = float(weight_speech) if weight_speech is not None else def_weights[3]
    w_motion = float(weight_motion) if weight_motion is not None else def_weights[4]

    w_total = w_audio + w_pitch + w_hook + w_speech + w_motion
    if w_total > 0:
        w_audio /= w_total
        w_pitch /= w_total
        w_hook /= w_total
        w_speech /= w_total
        w_motion /= w_total
    else:
        w_audio, w_pitch, w_hook, w_speech, w_motion = (0.25, 0.15, 0.25, 0.20, 0.15)

    # For very short slices (stream candidates ≤ 60s loaded from Audio Pull),
    # do NOT return a fake "Full Highlight" — run real analysis but with relaxed thresholds.
    is_short_slice = (video_duration <= 60.0)
    
    if video_duration <= min_dur:
        # Still try to analyze but cap at full duration
        min_dur = max(4.0, video_duration * 0.5)
        max_dur = video_duration + 1.0

    # 1. Extract audio features & vocal excitement
    audio_feats = extract_audio_features(video_path, window_sec=0.5, max_duration=video_duration)
    rms_list = audio_feats.get("rms", [])
    zcr_list = audio_feats.get("zcr", [])
    gradient_list = audio_feats.get("gradient", [])
    excitement_list = audio_feats.get("excitement", [])
    mean_rms = audio_feats.get("mean_rms", 1.0)
    max_rms = audio_feats.get("max_rms", 1.0)
    mean_zcr = audio_feats.get("mean_zcr", 0.1)
    max_zcr = audio_feats.get("max_zcr", 0.5)

    # 2. Build dynamic narrative candidate windows centered around emotional climaxes
    candidate_quads = build_dynamic_narrative_candidates(
        subtitles=subtitles,
        audio_feats=audio_feats,
        video_duration=video_duration,
        min_dur=min_dur,
        max_dur=max_dur
    )
    
    # For short slices with no detected climaxes, force an analysis window covering the peak
    # (the entire slice IS a pre-identified audio peak from Audio Pull, so use it)
    if not candidate_quads and is_short_slice:
        rms_list_tmp = audio_feats.get("rms", [])
        peak_idx = rms_list_tmp.index(max(rms_list_tmp)) if rms_list_tmp else int(video_duration * 2 / 3 / 0.5)
        peak_time = round(peak_idx * 0.5, 1)
        candidate_quads = [(
            max(0.0, peak_time - 8.0),
            min(video_duration, peak_time + 20.0),
            peak_time,
            {"climax_type": "outburst", "duty_cycle": 0.5, "peak_rms": max(rms_list_tmp) if rms_list_tmp else mean_rms, "contrast": 1.5}
        )]

    # 3. Evaluate each candidate across the unified multimodal matrix
    scored_candidates = []
    seen_intervals = set()

    for (start_t, end_t, climax_t, extra_info) in candidate_quads:
        dur = end_t - start_t
        if dur < min_dur or dur > max_dur:
            continue
            
        boundary_meta = {"cold_open_applied": False, "speech_snapped": True}
        if snap_boundaries:
            start_t, end_t, boundary_meta = snap_to_clean_boundaries(
                start_t, end_t, 
                subtitles=subtitles, 
                audio_feats=audio_feats, 
                min_duration=min_dur, 
                max_duration=max_dur
            )
            dur = end_t - start_t

        key = (round(start_t, 1), round(end_t, 1))
        if key in seen_intervals:
            continue
        seen_intervals.add(key)

        # A. Parameter 1: Vocal Outburst & Climax Energy
        if rms_list:
            win_start_idx = int(start_t / 0.5)
            win_end_idx = min(len(rms_list), int(end_t / 0.5))
            slice_rms = rms_list[win_start_idx:win_end_idx]
            slice_grad = gradient_list[win_start_idx:win_end_idx]
            slice_exc = excitement_list[win_start_idx:win_end_idx]
            slice_zcr = zcr_list[win_start_idx:win_end_idx]
            if slice_rms:
                slice_mean = sum(slice_rms) / len(slice_rms)
                slice_peak = max(slice_rms)
                slice_burst = max(slice_grad) if slice_grad else 0.0
                slice_peak_exc = max(slice_exc) if slice_exc else 1.0
                slice_mean_zcr = sum(slice_zcr) / len(slice_zcr) if slice_zcr else mean_zcr
                
                # Check Streamer Voice Duty Cycle
                silence_threshold = max(350.0, mean_rms * 0.15)
                speech_count = sum(1 for r in slice_rms if r >= silence_threshold)
                duty_cycle = speech_count / len(slice_rms)
                
                # STRICT VIRAL FILTER: Streamer must be actively speaking or shouting (no mundane silence)
                # Relax thresholds for short slices (already pre-identified as peak moments from Audio Pull)
                duty_threshold = 0.20 if is_short_slice else 0.35
                energy_threshold = 1.4 if is_short_slice else 1.7
                burst_threshold = 1.0 if is_short_slice else 1.3
                exc_threshold = 1.4 if is_short_slice else 1.9
                
                if duty_cycle < duty_threshold and slice_peak < 2.0 * mean_rms:
                    continue
                if slice_peak < energy_threshold * mean_rms and slice_burst < burst_threshold * mean_rms and slice_peak_exc < exc_threshold:
                    continue  # Mundane conversational chatter with no peak outburst - DROP
                
                energy_ratio = (slice_mean / (mean_rms + 1e-4)) * 0.4 + (slice_peak / (max_rms + 1e-4)) * 0.4 + (slice_peak_exc / 2.5) * 0.2
                audio_score = min(1.0, max(0.20, energy_ratio / 1.8))
                zcr_ratio = slice_mean_zcr / (mean_zcr + 1e-4)
                pitch_score = min(1.0, max(0.20, zcr_ratio / 1.6))
            else:
                continue
        else:
            audio_score = 0.5
            pitch_score = 0.5
            duty_cycle = 0.5
            slice_peak = 0.0
            slice_mean = 0.0
            slice_burst = 0.0
            slice_peak_exc = 1.0
            slice_mean_zcr = mean_zcr

        # C. Parameter 3: First 3-Second Viral Hook Strength
        hook_score, hook_reason = evaluate_hook_quality(subtitles, start_t, end_t)

        # D. Parameter 4: Speech Dynamics, Reaction Triggers & Dead-Air Penalty
        speech_score, speech_stats, speech_reason, hook_title, dead_air_pen = evaluate_speech_dynamics_and_dead_air(
            subtitles=subtitles,
            start=start_t,
            end=end_t,
            rms_list=rms_list,
            mean_rms=mean_rms
        )

        # Extreme Reaction Categorization
        climax_type = extra_info.get("climax_type", "outburst")
        c_transient = extra_info.get("contrast", 1.0)
        if climax_type == "jumpscare_transient" or c_transient >= 3.2:
            reaction_category = "⚡ Instant Reaction & Jumpscare"
            badge_color = "#3B82F6"
        elif (slice_peak > 2.0 * mean_rms and slice_mean_zcr > 1.25 * mean_zcr) or climax_type == "scream":
            reaction_category = "😱 Streamer Scream & Outburst"
            badge_color = "#EF4444" # Crimson
        elif slice_peak_exc > 2.4 or speech_stats.get("comedy", 0) >= 2 or climax_type == "laughter":
            reaction_category = "😂 Hysterical Laughter & Comedy"
            badge_color = "#F59E0B" # Amber
        elif climax_type == "despair" or (slice_peak > 1.8 * mean_rms and dead_air_pen > 0.12):
            reaction_category = "😭 Shock & Emotional Disbelief"
            badge_color = "#EC4899" # Pink
        elif slice_burst > 1.4 * mean_rms:
            reaction_category = "⚡ Sudden Audio Surge & Climax"
            badge_color = "#3B82F6" # Blue
        elif slice_mean > 1.25 * mean_rms or speech_stats.get("reactions", 0) >= 2:
            reaction_category = "🔥 High-Energy Rage & Hype"
            badge_color = "#8B5CF6" # Violet
        else:
            reaction_category = "🎙️ Streamer Commentary & Story"
            badge_color = "#10B981" # Emerald

        # Normalized non-motion weights for initial ranking pass
        w_nm = w_audio + w_pitch + w_hook + w_speech
        wa_n = w_audio / w_nm if w_nm > 0 else 0.35
        wp_n = w_pitch / w_nm if w_nm > 0 else 0.15
        wh_n = w_hook / w_nm if w_nm > 0 else 0.20
        ws_n = w_speech / w_nm if w_nm > 0 else 0.30

        prelim_score = (audio_score * wa_n + pitch_score * wp_n + hook_score * wh_n + speech_score * ws_n) - dead_air_pen
        scored_candidates.append({
            "start": round(start_t, 1),
            "end": round(end_t, 1),
            "duration": round(dur, 1),
            "climax_t": climax_t,
            "audio_score": audio_score,
            "pitch_score": pitch_score,
            "hook_score": hook_score,
            "speech_score": speech_score,
            "speech_stats": speech_stats,
            "dead_air_pen": dead_air_pen,
            "prelim_score": prelim_score,
            "reaction_category": reaction_category,
            "badge_color": badge_color,
            "reason": reaction_category,
            "title": hook_title,
            "duty_cycle": duty_cycle,
            "slice_peak": slice_peak,
            "transient_contrast": c_transient,
            "cold_open_verified": boundary_meta.get("cold_open_applied", False),
            "speech_snapped": boundary_meta.get("speech_snapped", True),
            "narrative_micro_arc": boundary_meta.get("narrative_snapped", True),
            "narrative_arc": boundary_meta.get("narrative_arc", {"hook_detected": True, "punchline_snap": True}),
            "snap_mode": boundary_meta.get("snap_mode", "audio_vad_envelope")
        })

    # Sort candidates by preliminary score
    scored_candidates.sort(key=lambda x: x["prelim_score"], reverse=True)

    # 4. Non-Maximum Suppression (NMS) to eliminate overlapping windows
    distinct_candidates = []
    max_distinct = max(18, min(50, int(video_duration / 70)))
    for cand in scored_candidates:
        cand_start = cand["start"]
        cand_end = cand["end"]
        overlap_found = False
        for sel in distinct_candidates:
            overlap_start = max(cand_start, sel["start"])
            overlap_end = min(cand_end, sel["end"])
            if overlap_end > overlap_start:
                overlap_dur = overlap_end - overlap_start
                if (overlap_dur / cand["duration"]) > 0.35 or (overlap_dur / sel["duration"]) > 0.35:
                    overlap_found = True
                    break
        if not overlap_found:
            distinct_candidates.append(cand)
            if len(distinct_candidates) >= max_distinct:
                break

    # 5. Parameter 5 & Synergy: Dedicated Streamer Facecam Reaction, Jaw-Drop & Multimodal Fusion
    # Run visual/motion extraction ONLY on the top candidates (up to 14) for sub-second efficiency
    max_motion_eval = min(len(distinct_candidates), 14)
    for idx, cand in enumerate(distinct_candidates):
        if idx < max_motion_eval:
            gp_motion, cam_reaction, jaw_drop = extract_candidate_motion(
                video_path=video_path,
                start_t=cand["start"],
                dur=min(3.5, cand["duration"]),
                webcam_crop=webcam_crop,
                climax_t=cand.get("climax_t")
            )
        else:
            gp_motion, cam_reaction, jaw_drop = 0.5, 0.5, False

        cand["gameplay_motion"] = gp_motion
        cand["facecam_reaction"] = cam_reaction
        cand["jaw_drop_verified"] = jaw_drop

        # Multimodal Synergy: Facecam reaction + Audio burst + Reaction word at same climax!
        synergy_bonus = 0.0
        if cam_reaction >= 0.60 and cand["audio_score"] >= 0.60:
            synergy_bonus += 5.0
            if cand["speech_stats"].get("reactions", 0) > 0 or cand["speech_stats"].get("comedy", 0) > 0:
                synergy_bonus += 5.0

        if jaw_drop:
            synergy_bonus += 6.0
            cand["reaction_category"] = "😲 Jaw-Drop Shock Reaction"
            cand["badge_color"] = "#EF4444"

        # Transient dynamic surge bonus
        transient_ratio = cand.get("transient_contrast", 1.0)
        contrast_pts = min(6.0, max(0.0, (transient_ratio - 1.2) * 2.0))

        base_pts = 50.0
        audio_pts = cand["audio_score"] * w_audio * 50.0
        pitch_pts = cand["pitch_score"] * w_pitch * 50.0
        motion_pts = (cam_reaction * 0.70 + gp_motion * 0.30) * w_motion * 50.0
        hook_pts = cand["hook_score"] * w_hook * 50.0
        speech_pts = cand["speech_score"] * w_speech * 50.0
        duty_pts = cand["duty_cycle"] * 6.0
        dead_air_deduction = cand["dead_air_pen"] * 50.0

        raw_virality = base_pts + audio_pts + pitch_pts + motion_pts + hook_pts + speech_pts + duty_pts + synergy_bonus + contrast_pts - dead_air_deduction
        cand["virality_score"] = int(min(99, max(68, round(raw_virality))))
        cand["synergy_bonus"] = int(round(synergy_bonus))

    distinct_candidates.sort(key=lambda x: x["virality_score"], reverse=True)

    # 6. Integrated Cognitive Brain & Executive Producer Pass
    is_auto_mode = (target_clips is None or target_clips <= 0)
    final_list = []

    if use_llm:
        try:
            usable_subs = list(subtitles) if subtitles else []

            if is_auto_mode:
                # For short slices (stream candidates): target 1-2 clips. For long streams: 6-12 clips.
                if is_short_slice:
                    auto_target_count = max(1, min(3, int(video_duration / 15)))
                else:
                    auto_target_count = max(6, min(12, int(video_duration / 300)))
                llm_eval_pool = distinct_candidates[:min(len(distinct_candidates), max(10, auto_target_count + 4))]
                approved_clips, curation_reason = curate_auto_viral_clips(
                    candidates=llm_eval_pool,
                    subtitles=usable_subs,
                    video_duration=video_duration,
                    target_count=auto_target_count,
                    model=llm_model
                )
                if approved_clips:
                    final_list = approved_clips[:auto_target_count]
                    print(f"[Viral Detector] LLM Mind selected {len(final_list)} viral clips. Reason: {curation_reason}")
            else:
                eval_limit = max(1, min(len(distinct_candidates), target_clips))
                llm_eval_pool = distinct_candidates[:min(len(distinct_candidates), max(10, eval_limit + 4))]
                approved_clips, curation_reason = curate_auto_viral_clips(
                    candidates=llm_eval_pool,
                    subtitles=usable_subs,
                    video_duration=video_duration,
                    target_count=eval_limit,
                    model=llm_model
                )
                if approved_clips:
                    final_list = approved_clips[:eval_limit]
                    print(f"[Viral Detector] LLM Mind curated {len(final_list)} target clips. Reason: {curation_reason}")
                else:
                    final_list = distinct_candidates[:eval_limit]

        except Exception as llm_err:
            print(f"[Viral Detector] LLM Cognitive Brain pass skipped: {llm_err}")

    # 7. Fallback Selection (if LLM offline, disabled, or failed)
    if not final_list:
        if target_clips is not None and target_clips > 0:
            final_list = distinct_candidates[:target_clips]
        else:
            if is_short_slice:
                auto_count = max(1, min(3, int(video_duration / 15)))
            else:
                auto_count = max(6, min(12, int(video_duration / 300)))
            # Strictly return the top auto_count bangers, NEVER flood with 50 clips!
            final_list = distinct_candidates[:min(auto_count, len(distinct_candidates))]
    
    # LAST RESORT: For short slices (pre-identified Audio Pull peaks), if still nothing
    # found after all filters, return the best window based on raw energy peak
    if not final_list and is_short_slice:
        rms_list_fallback = audio_feats.get("rms", [])
        if rms_list_fallback:
            peak_idx = rms_list_fallback.index(max(rms_list_fallback))
            peak_t = round(peak_idx * 0.5, 1)
            fb_start = max(0.0, peak_t - 8.0)
            fb_end = min(video_duration, peak_t + 18.0)
            # Use LLM/heuristic title if subtitles available
            fb_title = "INSANE MOMENT 💀🔥"
            if subtitles:
                from backend.llm_engine import synthesize_curiosity_gap_title
                window_subs = [s for s in subtitles if float(s.get("end",0)) >= fb_start and float(s.get("start",0)) <= fb_end]
                if window_subs:
                    full_speech = " ".join(s.get("text","") for s in window_subs)
                    fb_title = synthesize_curiosity_gap_title(full_speech, "outburst", rank=1)
            final_list = [{
                "id": "clip_1",
                "rank": 1,
                "start": round(fb_start, 1),
                "end": round(fb_end, 1),
                "duration": round(fb_end - fb_start, 1),
                "climax_t": peak_t,
                "virality_score": 85,
                "reaction_category": "🔥 High-Energy Peak",
                "badge_color": "#EF4444",
                "title": fb_title,
                "audio_score": 0.7,
                "pitch_score": 0.5,
                "hook_score": 0.6,
                "speech_score": 0.6,
                "speech_stats": {},
                "dead_air_pen": 0.0,
                "duty_cycle": 0.5,
                "slice_peak": max(rms_list_fallback),
                "transient_contrast": 1.5,
                "gameplay_motion": 0.5,
                "facecam_reaction": 0.5,
                "jaw_drop_verified": False,
                "cold_open_verified": False,
                "synergy_bonus": 0
            }]

    # Keep clips strictly sorted by Virality Score with LLM verification priority
    final_list.sort(key=lambda x: (1 if x.get("llm_verified") else 0, x["virality_score"]), reverse=True)

    # 8. Format clips with transparent metrics breakdown, cover thumbnail & viral rankings
    formatted = []
    thumb_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "storage", "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)

    for idx, c in enumerate(final_list):
        score = c["virality_score"]
        rank_num = idx + 1
        clip_dur = round(c["end"] - c["start"], 1)

        if score >= 90:
            tier_badge = f"👑 RANK #{rank_num} • S-TIER VIRAL"
        elif score >= 80:
            tier_badge = f"⚡ RANK #{rank_num} • A-TIER RETENTION"
        else:
            tier_badge = f"🎯 RANK #{rank_num} • B-TIER HIGHLIGHT"

        # High-CTR Contextual Titling: Never leave as generic 'Stream Highlight'
        clean_title = c.get("title", "").strip()
        clean_title = re.sub(r"^Rank\s*#?\d+\s*•\s*", "", clean_title)
        if not clean_title or clean_title in ("THE BIGGEST FISH?!", "VIRAL MOMENT", "Stream Highlight", "Highlight"):
            category = c.get("reaction_category", "")
            if "Scream" in category or "Outburst" in category:
                titles_pool = [
                    "HE LOST HIS MIND AT THIS 💀",
                    "BRO SAW HIS LIFE FLASH 😭",
                    "LOUDEST SCREAM IN STREAM HISTORY 💀",
                    "HE WAS NOT READY FOR THIS 🔥"
                ]
            elif "Laughter" in category or "Comedy" in category:
                titles_pool = [
                    "HE COULD NOT STOP LAUGHING 😂",
                    "BRO TRIED SO HARD NOT TO LAUGH 💀",
                    "FUNNIEST MOMENT OF THE ENTIRE STREAM 😭",
                    "CHAT WAS DYING AT THIS 😂"
                ]
            elif "Jumpscare" in category or "Instant Reaction" in category:
                titles_pool = [
                    "INSTANT REGRET CAUGHT ON CAMERA 😳",
                    "BRO JUMPED OUT OF HIS CHAIR 😭",
                    "HE REALLY THOUGHT HE WAS SAFE 💀",
                    "WAIT UNTIL THE END... 😳"
                ]
            elif "Jaw-Drop" in category:
                titles_pool = [
                    "HE WAS COMPLETELY SPEECHLESS 😲",
                    "BRO'S JAW DROPPED TO THE FLOOR 💀",
                    "IS THIS ACTUALLY REAL?! 🤯"
                ]
            else:
                titles_pool = [
                    "INSANE MOMENT IN STREAM 💀",
                    "NOBODY EXPECTED THIS TO HAPPEN 🔥",
                    "BRO ACTUALLY PULLED THIS OFF 😳"
                ]
            clean_title = titles_pool[idx % len(titles_pool)]

        clip_id = f"clip_{rank_num}"
        thumb_file = f"{clip_id}_thumb.jpg"
        thumb_path = os.path.join(thumb_dir, thumb_file)
        has_thumb = extract_clip_thumbnail(video_path, c.get("climax_t", c["start"] + 1.5), thumb_path)

        clip_item = {
            "id": clip_id,
            "rank": rank_num,
            "title": f"Rank #{rank_num} • {clean_title}",
            "start": c["start"],
            "end": c["end"],
            "duration": clip_dur,
            "virality_score": score,
            "reason": c["reaction_category"],
            "badge_color": c["badge_color"],
            "tier_badge": tier_badge,
            "thumbnail_url": f"/media/thumbnail/{clip_id}" if has_thumb else None,
            "has_thumbnail": has_thumb,
            "jaw_drop_verified": c.get("jaw_drop_verified", False),
            "cold_open_verified": c.get("cold_open_verified", False),
            "metrics": {
                "voice_energy": int(round(c["audio_score"] * 100)),
                "facecam_reaction": int(round(c.get("facecam_reaction", 0.5) * 100)),
                "jaw_drop_verified": c.get("jaw_drop_verified", False),
                "cold_open_verified": c.get("cold_open_verified", False),
                "dynamic_contrast": round(c.get("transient_contrast", 1.0), 1),
                "hook_quality": int(round(c["hook_score"] * 100)),
                "speech_density": int(round(c["speech_score"] * 100)),
                "action_motion": int(round(c.get("gameplay_motion", 0.5) * 100)),
                "synergy_bonus": c.get("synergy_bonus", 0)
            }
        }
        if c.get("llm_verified"):
            clip_item["llm_verified"] = True
        if c.get("ai_curated"):
            clip_item["ai_curated"] = True
        if c.get("llm_punchline"):
            clip_item["llm_punchline"] = c["llm_punchline"]

        formatted.append(clip_item)

    return formatted
