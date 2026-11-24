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

        # Build clean character transcript separated by "|" while preserving indices of mapped words
        token_indices = []
        mapped_word_indices = []
        sep_id = _DICTIONARY.get("|", 0)

        for w_idx, w_item in enumerate(words):
            w_text = re.sub(r'[^a-zA-Z0-9\']', '', str(w_item.get("word", "")).upper()).strip()
            if not w_text:
                continue
            char_toks = [_DICTIONARY[ch] for ch in w_text if ch in _DICTIONARY]
            if not char_toks:
                continue

            if token_indices:
                token_indices.append(sep_id)

            token_indices.extend(char_toks)
            mapped_word_indices.append(w_idx)

        if not token_indices:
            return words

        targets = torch.tensor([token_indices], dtype=torch.int32)

        # Use torchaudio.functional.forced_align + merge_tokens if available
        if hasattr(torchaudio.functional, "forced_align") and hasattr(torchaudio.functional, "merge_tokens"):
            try:
                aligned_tokens, scores = torchaudio.functional.forced_align(
                    emissions,
                    targets,
                    blank=0
                )
                token_spans = torchaudio.functional.merge_tokens(aligned_tokens[0], scores[0])

                word_groups = []
                current_group = []
                for span in token_spans:
                    if span.token == sep_id:
                        if current_group:
                            word_groups.append(current_group)
                            current_group = []
                    else:
                        current_group.append(span)
                if current_group:
                    word_groups.append(current_group)

                if len(word_groups) == len(mapped_word_indices):
                    aligned_words = [dict(w) for w in words]
                    for grp, orig_idx in zip(word_groups, mapped_word_indices):
                        new_s = round(grp[0].start * time_per_frame, 3)
                        new_e = round(grp[-1].end * time_per_frame, 3)
                        aligned_words[orig_idx]["start"] = max(0.0, new_s)
                        aligned_words[orig_idx]["end"] = max(aligned_words[orig_idx]["start"] + 0.05, new_e)
                    return aligned_words
            except Exception as inner_e:
                print(f"[WARN] Wav2Vec2 token alignment skipped: {inner_e}")

        return words
    except Exception as e:
        print(f"[WARN] Wav2Vec2 forced alignment skipped: {e}")
        return words
