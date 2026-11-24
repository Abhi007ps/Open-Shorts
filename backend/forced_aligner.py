"""
OpenShorts Wav2Vec2 Phoneme Forced Aligner.
Isolated optional plugin providing frame-level character/phoneme alignment (~20ms accuracy).
Lazy-loads torchaudio pipelines when PyTorch is installed, falling back gracefully on any error.
"""

import os
import re
import wave
import threading
from typing import List, Dict, Any, Optional

_ALIGNER_LOCK = threading.Lock()
_BUNDLE = None
_MODEL = None
_DICTIONARY = None

def is_forced_aligner_available() -> bool:
    """Returns True only if torch and torchaudio import cleanly."""
    try:
        import torch
        import torchaudio
        return True
    except Exception:
        return False

def align_words_wav2vec2(
    wav_path: str,
    words: List[Dict[str, Any]],
    language: str = "en"
) -> List[Dict[str, Any]]:
    """
    Refines word timestamps using Wav2Vec2 CTC frame emissions.
    Only runs when language is English or auto, audio duration <= 120s,
    and PyTorch/torchaudio are available.
    Returns original words unmodified if aligner is unavailable or encounters any error.
    """
    if not words or not wav_path or not os.path.isfile(wav_path):
        return words

    lang_clean = (language or "en").lower().split("-")[0]
    if lang_clean not in ("en", "auto"):
        return words

    # Fast duration check via wave module to avoid loading multi-hour files
    try:
        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            rate = wf.getframerate()
            dur = n_frames / float(rate)
            if dur > 120.0 or dur < 0.3:
                return words
    except Exception:
        return words

    if not is_forced_aligner_available():
        return words

    global _BUNDLE, _MODEL, _DICTIONARY
    try:
        import torch
        import torchaudio

        with _ALIGNER_LOCK:
            if _MODEL is None:
                _BUNDLE = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
                _MODEL = _BUNDLE.get_model()
                _MODEL.eval()
                _DICTIONARY = _BUNDLE.get_dict()

        # Load audio (16kHz mono)
        waveform, sample_rate = torchaudio.load(wav_path)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        if sample_rate != _BUNDLE.sample_rate:
            resampler = torchaudio.transforms.Resample(sample_rate, _BUNDLE.sample_rate)
            waveform = resampler(waveform)

        with torch.inference_mode():
            emissions, _ = _MODEL(waveform)
            emissions = torch.log_softmax(emissions, dim=-1)

        emission = emissions[0].cpu().detach()
        num_frames = emission.shape[0]
        time_per_frame = dur / max(1, num_frames)

        # Build clean character transcript separated by "|"
        cleaned_words = []
        token_indices = []
        word_spans = []
        curr_tok_idx = 0

        for w_item in words:
            w_text = re.sub(r'[^a-zA-Z0-9\']', '', str(w_item.get("word", "")).upper()).strip()
            if not w_text:
                continue
            char_toks = []
            for ch in w_text:
                if ch in _DICTIONARY:
                    char_toks.append(_DICTIONARY[ch])
            if not char_toks:
                continue

            if token_indices:
                token_indices.append(_DICTIONARY.get("|", 0))
                curr_tok_idx += 1

            w_start_idx = curr_tok_idx
            token_indices.extend(char_toks)
            curr_tok_idx += len(char_toks)
            w_end_idx = curr_tok_idx

            cleaned_words.append(w_item)
            word_spans.append((w_start_idx, w_end_idx))

        if not token_indices:
            return words

        targets = torch.tensor([token_indices], dtype=torch.int32)

        # Use torchaudio.functional.forced_align if available
        aligned_spans = None
        if hasattr(torchaudio.functional, "forced_align"):
            try:
                align_out = torchaudio.functional.forced_align(
                    emissions,
                    targets,
                    blank=0
                )
                aligned_tokens = align_out[0][0].tolist()
                
                # Group frames per token index
                token_frames = {}
                for f_idx, t_idx in enumerate(aligned_tokens):
                    if t_idx < 0:
                        continue
                    if t_idx not in token_frames:
                        token_frames[t_idx] = []
                    token_frames[t_idx].append(f_idx)

                aligned_words = []
                for w_idx, w_item in enumerate(cleaned_words):
                    s_tok, e_tok = word_spans[w_idx]
                    w_frames = []
                    for t in range(s_tok, e_tok):
                        if t in token_frames:
                            w_frames.extend(token_frames[t])

                    if w_frames:
                        new_s = round(min(w_frames) * time_per_frame, 3)
                        new_e = round((max(w_frames) + 1) * time_per_frame, 3)
                        aligned_words.append({
                            "word": w_item["word"],
                            "start": max(0.0, new_s),
                            "end": max(new_s + 0.05, new_e)
                        })
                    else:
                        aligned_words.append(dict(w_item))
                return aligned_words
            except Exception:
                pass

        return words
    except Exception as e:
        print(f"[WARN] Wav2Vec2 forced alignment skipped: {e}")
        return words
