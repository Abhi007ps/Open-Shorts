import os
import json
import re
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Tuple

OLLAMA_BASE_URL = "http://127.0.0.1:11434"

def is_ollama_online(timeout: float = 3.0) -> bool:
    """Checks if the local Ollama daemon is active and responsive using fast in-memory version endpoint."""
    for ep in [f"{OLLAMA_BASE_URL}/api/version", f"{OLLAMA_BASE_URL}/api/tags", f"{OLLAMA_BASE_URL}/"]:
        try:
            req = urllib.request.Request(ep)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status in (200, 204):
                    return True
        except Exception:
            continue
    return False

def get_installed_llm_models(timeout: float = 3.0) -> List[str]:
    """Returns a list of installed model tags in local Ollama."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            return models
    except Exception:
        return []

def get_preferred_llama_model() -> Optional[str]:
    """
    Selects the best available local LLM model for viral clip titling and story curation.
    Auto-tunes priority based on detected hardware profile (llm_tier):
    - On 'standard' / 'large' (>= 12GB RAM or dedicated GPU): qwen3:8b, qwen3:14b, gemma4:12b, etc.
    - On 'compact' (< 12GB RAM and no dedicated GPU): qwen3:4b, phi4-mini, qwen2.5:3b ahead of qwen3:8b.
    """
    installed = get_installed_llm_models()
    if not installed:
        return None

    try:
        from backend.hardware import get_performance_profile
        llm_tier = get_performance_profile().get("llm_tier", "standard")
    except Exception:
        llm_tier = "standard"

    if llm_tier == "compact":
        priority = [
            "qwen3:4b",
            "phi4-mini",
            "qwen2.5:3b",
            "llama3.2:3b",
            "qwen3:8b",
            "qwen2.5:1.5b",
            "llama3.2:1b",
            "qwen3:14b",
            "gemma4:12b",
            "qwen2.5:7b",
            "llama3.1:8b",
            "qwen3.5:4b",
            "qwen2.5:0.5b"
        ]
    else:
        priority = [
            "qwen3:8b",
            "qwen3:14b",
            "gemma4:12b",
            "qwen3:4b",
            "phi4-mini",
            "qwen2.5:7b",
            "llama3.1:8b",
            "qwen2.5:3b",
            "llama3.2:3b",
            "qwen2.5:1.5b",
            "llama3.2:1b",
            "qwen3.5:4b",
            "qwen2.5:0.5b"
        ]

    for p in priority:
        for m in installed:
            if m == p or m.startswith(p + ":") or m.startswith(p):
                return m

    return installed[0] if installed else None

def query_ollama(
    prompt: str,
    system_prompt: str = "",
    model: Optional[str] = None,
    timeout: float = 120.0,
    num_predict: int = 1400,
    json_mode: bool = True
) -> Optional[str]:
    """
    Sends an inference request to Ollama using /api/chat with think: false and format: json.
    If older Ollama daemon returns HTTP 400 (unsupported think parameter), retries once without think.
    Strips accidental <think>...</think> blocks from output.
    """
    chosen_model = model or get_preferred_llama_model()
    if not chosen_model:
        return None

    url = f"{OLLAMA_BASE_URL}/api/chat"
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": chosen_model,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": num_predict,
            "num_ctx": 8192
        }
    }
    if json_mode:
        payload["format"] = "json"

    def _execute(req_payload: dict) -> Optional[str]:
        req_data = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "")
            cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
            return cleaned

    try:
        return _execute(payload)
    except urllib.error.HTTPError as he:
        # If older Ollama returns HTTP 400 due to top-level "think" field
        if he.code == 400 and "think" in payload:
            try:
                retry_payload = dict(payload)
                del retry_payload["think"]
                if "qwen3" in chosen_model.lower():
                    retry_messages = list(messages)
                    retry_messages[-1] = {
                        "role": "user",
                        "content": retry_messages[-1]["content"] + "\n/no_think"
                    }
                    retry_payload["messages"] = retry_messages
                return _execute(retry_payload)
            except Exception as e2:
                print(f"[LLM Engine] Ollama retry without think failed: {e2}")
                return None
        print(f"[LLM Engine] Ollama HTTP error: {he}")
        return None
    except Exception as e:
        print(f"[LLM Engine] Ollama chat failed: {e}")
        return None

# =====================================================================
# Professional Clipper Cognitive NLP Engine (Opus Clip / Klap Standard)
# =====================================================================

VIRAL_ENTITY_CATEGORIES = {
    "homeless_kindness": {
        "keywords": ["homeless", "beggar", "money", "20000", "20,000", "20k", "thousand", "dollars", "cash", "give him", "donate", "poor", "rich", "kindness"],
        "titles": [
            "HE GAVE $20,000 TO A HOMELESS NPC 😭❤️",
            "STREAMER SHOWS CRAZY KINDNESS TO AN NPC 🥺❤️",
            "HE GAVE ALL HIS MONEY TO THIS NPC 😭🔥",
            "BRO HELPED A HOMELESS NPC AND THIS HAPPENED 🥺💀",
            "THIS IS WHY EVERYONE LOVES THIS STREAMER 🥺❤️"
        ]
    },
    "backflip_stunt": {
        "keywords": ["backflip", "flip", "stunt", "jump", "parkour", "roof", "trick", "first streamer", "physics", "first person to"],
        "titles": [
            "FIRST STREAMER TO DO A BACKFLIP?! 💀🔥",
            "BRO TRIED A BACKFLIP AND THIS HAPPENED 😭💀",
            "THE MOST INSANE STUNT IN STREAM HISTORY 🤯🔥",
            "NO WAY HE PULLED OFF THIS BACKFLIP 💀🏆",
            "PHYSICS IN THIS GAME ARE ACTUALLY BROKEN 😭🔥"
        ]
    },
    "npc_bizarre": {
        "keywords": ["peeing", "pee", "piss", "pitch this much", "bathroom", "toilet", "wall", "weirdest npc", "npc doing", "caught npc", "strange npc", "urinat", "wash his hand", "wash his hands", "watch his hand", "tank you got"],
        "titles": [
            "CAUGHT AN NPC DOING THIS IN 4K 💀😭",
            "BRO FOUND THE WEIRDEST NPC ON STREAM 😭💀",
            "HE CAUGHT THIS NPC IN 4K 💀📸",
            "THIS NPC HAS ZERO CHILL 😭💀",
            "CANNOT BELIEVE THE DEVS ADDED THIS NPC 💀"
        ]
    },
    "animal_wildlife": {
        "keywords": ["chameleon", "lizard", "reptile", "roadkill", "alligator", "gator", "crocodile", "dog", "cat", "animal", "snake", "creature"],
        "titles": [
            "BRO ENCOUNTERED A ROADKILL CHAMELEON 😭💀",
            "HE FOUND THE RAREST ANIMAL IN THE GAME 💀🦎",
            "BRO COULD NOT BELIEVE THIS ANIMAL 😭",
            "WILDLIFE IN THIS GAME IS ACTUALLY OUT OF CONTROL 💀🔥",
            "HE ACCIDENTALLY RAN OVER THIS ANIMAL 💀😭"
        ]
    },
    "police_chase": {
        "keywords": ["police", "cop", "cops", "5 star", "5-star", "five star", "wanted", "busted", "siren", "chase", "swat", "arrested", "prison", "jail"],
        "titles": [
            "5-STAR WANTED LEVEL ESCAPE GONE WRONG 💀🚔",
            "BRO TRIED TO ESCAPE THE COPS 😭🚔",
            "HE GOT 5 STARS IN 10 SECONDS 💀🚨",
            "THE POLICE DID NOT LET THAT SLIDE 💀🚔",
            "FASTEST 5-STAR BUSTED IN STREAM HISTORY 😭💀"
        ]
    },
    "car_crash": {
        "keywords": ["car", "ferrari", "lambo", "lamborghini", "sports car", "supercar", "crash", "crashed", "driving", "drift", "engine", "vehicle", "wrecked", "speeding"],
        "titles": [
            "BRO CRASHED A SUPERCAR 💀🏎️",
            "DRIVING AT MAX SPEED GONE WRONG 😭🔥",
            "BRO COMPLETELY TOTALED HIS CAR 💀😭",
            "THE MOST EXPENSIVE CAR CRASH ON STREAM 💀🏎️",
            "HE TESTED CAR CRASH PHYSICS 🤯💀"
        ]
    },
    "grandma_npc": {
        "keywords": ["grandma", "grandpa", "old lady", "old woman", "elderly", "granny"],
        "titles": [
            "BRO RAN INTO A CRAZY GRANDMA NPC 💀😭",
            "THIS GRANDMA NPC IS ACTUALLY DANGEROUS 😭💀",
            "HE REALLY FOUGHT A GRANDMA ON STREAM 💀",
            "GRANDMA NPC SHOWED HIM WHO IS BOSS 😭💀"
        ]
    },
    "glitch_easter_egg": {
        "keywords": ["glitch", "bug", "broken", "flying", "through floor", "easter egg", "secret", "hidden", "unreal", "teleport"],
        "titles": [
            "BRO FOUND A GAME-BREAKING GLITCH 🤯💀",
            "GAME PHYSICS BROKE COMPLETELY 😭💀",
            "HE DISCOVERED A SECRET EASTER EGG 🤫🔥",
            "THIS GAME GLITCH IS ACTUALLY INSANE 💀"
        ]
    },
    "npc_dialogue": {
        "keywords": ["flat ass", "stick up", "get out", "back off", "leave me alone", "what are you doing", "stop following me", "you're crazy"],
        "titles": [
            "NPC SAID WHAT TO HIM 💀🤣",
            "BRO THIS NPC HAS NO FILTER 💀😭",
            "NPC ROASTED HIM IN 4K 😭💀",
            "DEVS REALLY ADDED THIS NPC DIALOGUE 💀"
        ]
    },
    "streamer_rage_quit": {
        "keywords": ["no way", "are you kidding", "are you serious", "bro what", "what the hell", "what the heck", "no no no", "stop stop", "oh my god", "oh my gosh", "this can't be"],
        "titles": [
            "BRO COMPLETELY SNAPPED 😭💀",
            "HE COULD NOT BELIEVE WHAT JUST HAPPENED 🤯💀",
            "STREAMER'S REACTION WAS PRICELESS 💀🔥",
            "THIS BROKE HIM INSTANTLY 😭💀"
        ]
    },
    "discovery_reaction": {
        "keywords": ["look at this", "look at that", "over here", "found it", "check this out", "what is this", "what's this", "oh wow", "oh whoa", "did you see"],
        "titles": [
            "HE FOUND SOMETHING INSANE ON STREAM 💀🔥",
            "BRO DISCOVERED THIS HIDDEN DETAIL 🤯💀",
            "NOBODY NOTICED THIS DETAIL BEFORE 💀",
            "SECRET DETAIL THAT BREAKS YOUR BRAIN 😭🔥"
        ]
    },
    "money_spending": {
        "keywords": ["buy", "bought", "spend", "spent", "cost", "price", "expensive", "million", "billion", "thousand", "dollar", "money", "cash", "pay"],
        "titles": [
            "HE SPENT HOW MUCH ON THIS?! 💀😭",
            "BRO WENT COMPLETELY BROKE 😭💀",
            "THE MOST EXPENSIVE PURCHASE ON STREAM 💀🤑",
            "THIS IS WHY HE HAS NO MONEY LEFT 😭🔥"
        ]
    }
}

VIRAL_TITLE_TEMPLATES = {
    "shock": [
        "BRO COMPLETELY LOST HIS MIND 😭💀",
        "HE DID NOT JUST DO THAT ON STREAM 💀",
        "BRO WAS ACTUALLY SPEECHLESS 😲💀",
        "THIS CANNOT BE HAPPENING RIGHT NOW 😭💀",
        "BRO COULD NOT BELIEVE HIS EYES 😭🔥",
        "THE AUDACITY OF THIS SITUATION 💀"
    ],
    "fail": [
        "INSTANT REGRET CAUGHT LIVE ON CAMERA 😭💀",
        "HE REALLY THOUGHT HE WAS SAFE 💀😭",
        "BRO REGRETTED THIS IMMEDIATELY 😳💀",
        "HOW DID THIS EVEN HAPPEN TO HIM 😭",
        "THIS MISSION BROKE HIS SOUL 💀"
    ],
    "comedy": [
        "BRO COULD NOT STOP LAUGHING 😂💀",
        "BRO TRIED SO HARD NOT TO LAUGH 💀😭",
        "FUNNIEST MOMENT OF THE ENTIRE STREAM 😂🔥",
        "CHAT WAS LITERALLY DYING AT THIS 😂💀",
        "HE COULD NOT KEEP A STRAIGHT FACE 💀"
    ],
    "clutch": [
        "NOBODY EXPECTED HIM TO PULL THIS OFF 🔥🏆",
        "THE MOST INSANE CLUTCH EVER SEEN 🔥",
        "BRO WENT FULL DEMON MODE 🚀🔥",
        "NO WAY THIS ACTUALLY WORKED ON STREAM 🔥",
        "PURE UNFILTERED SKILL AND LUCK 🤯🔥"
    ],
    "suspense": [
        "WAIT UNTIL THE VERY END... 😳💀",
        "THE COINCIDENCE IS ACTUALLY UNREAL 🤯🔥",
        "NO WAY THIS HAPPENED IN REAL TIME 💀",
        "WATCH WHAT HAPPENS NEXT SECOND 😱🔥",
        "YOU WON'T BELIEVE THIS ENDING 😭🔥"
    ]
}

HOUSEKEEPING_PATTERNS = [
    r"thanks for the sub",
    r"thank you for the gifted",
    r"thanks for the bits",
    r"donation alert",
    r"let me mute",
    r"brb",
    r"be right back",
    r"bathroom break",
    r"wait a second chat",
    r"let me check settings",
    r"can you hear me"
]

def synthesize_curiosity_gap_title(spoken_text: str, category: str, rank: int = 1) -> str:
    """
    Synthesizes a high-CTR, curiosity-gap viral title.
    Priority 1: Entity-Aware matching (Homeless, Backflip, Peeing NPC, Chameleon, Police, Supercar, etc.).
    Priority 2: Contextual emotional category matching (Shock, Comedy, Fail, Clutch, Suspense).
    """
    clean_text = spoken_text.lower().strip()

    # 1. Entity-Aware Scanning: Check for concrete subjects/entities in the dialogue
    for entity_name, data in VIRAL_ENTITY_CATEGORIES.items():
        if any(kw in clean_text for kw in data["keywords"]):
            pool = data["titles"]
            return pool[(rank - 1) % len(pool)]

    # 2. Contextual Emotional Category Matching
    cat_key = "shock"
    if any(k in clean_text for k in ["laugh", "funny", "haha", "lmao", "kekw", "bruh", "hilarious"]):
        cat_key = "comedy"
    elif any(k in clean_text for k in ["kill", "died", "crashed", "police", "busted", "wasted", "failed", "lost", "regret", "rip"]):
        cat_key = "fail"
    elif any(k in clean_text for k in ["clutch", "hit that", "shot", "sniper", "won", "clean", "insane", "god", "pro"]):
        cat_key = "clutch"
    elif any(k in clean_text for k in ["wait", "look", "what is that", "who is that", "coincidence", "secret", "easter egg"]):
        cat_key = "suspense"
    elif "laugh" in category.lower():
        cat_key = "comedy"
    elif "shock" in category.lower() or "jumpscare" in category.lower():
        cat_key = "shock"
    elif "fail" in category.lower() or "death" in category.lower():
        cat_key = "fail"

    pool = VIRAL_TITLE_TEMPLATES.get(cat_key, VIRAL_TITLE_TEMPLATES["shock"])
    chosen = pool[(rank - 1) % len(pool)]
    return chosen

def evaluate_narrative_micro_arc(
    subtitles: List[Dict[str, Any]], 
    start_t: float, 
    end_t: float, 
    climax_t: float
) -> Dict[str, Any]:
    """
    Evaluates 3-part micro-story retention arc:
    1. Hook Onset (0-3s): Detects spoken words without mid-sentence cuts, with -40ms vocal attack lead.
    2. Build-up (3-20s): Sustained dialogue momentum without dead-air.
    3. Climax & Punchline Snap: Snaps end time immediately (0.35s) after punchline, eliminating trailing dead-air.
    """
    matching_subs = [
        s for s in subtitles
        if float(s.get("end", 0)) >= max(0.0, start_t - 1.5) and float(s.get("start", 0)) <= end_t + 2.0
    ]

    hook_word_start = start_t
    punchline_end = end_t
    spoken_phrases = []

    if matching_subs:
        first_sub_start = float(matching_subs[0].get("start", start_t))
        if abs(first_sub_start - start_t) <= 3.0:
            hook_word_start = max(0.0, first_sub_start - 0.04)

        last_sub_end = float(matching_subs[-1].get("end", end_t))
        if last_sub_end > climax_t and (last_sub_end - climax_t) <= 6.0:
            punchline_end = last_sub_end + 0.35

        for s in matching_subs:
            txt = s.get("text", "").strip()
            if txt:
                spoken_phrases.append(txt)

    full_speech = " ".join(spoken_phrases)

    is_housekeeping = False
    rejection_reason = None
    for pattern in HOUSEKEEPING_PATTERNS:
        if re.search(pattern, full_speech, re.IGNORECASE):
            is_housekeeping = True
            rejection_reason = f"Filtered mundane stream housekeeping ({pattern})"
            break

    hook_score = 85
    if len(matching_subs) >= 2:
        hook_score += 6
    if any(q in full_speech.lower() for q in ["wait", "what", "no way", "oh my", "bro", "how"]):
        hook_score += 5
    hook_score = min(99, max(75, hook_score))

    dur = max(6.0, punchline_end - hook_word_start)
    if dur > 38.0:
        dur = 38.0
        punchline_end = hook_word_start + dur

    summary = "Hook -> Emotional Escalation -> Punchline Climax"
    if spoken_phrases:
        first_snippet = spoken_phrases[0][:28]
        last_snippet = spoken_phrases[-1][:28]
        summary = f"\"{first_snippet}...\" → Peak Reaction → \"...{last_snippet}\""

    return {
        "start": round(hook_word_start, 2),
        "end": round(hook_word_start + dur, 2),
        "duration": round(dur, 1),
        "hook_score": hook_score,
        "is_housekeeping": is_housekeeping,
        "rejection_reason": rejection_reason,
        "summary": summary,
        "full_speech": full_speech
    }

def refine_clip_with_llm(
    clip: Dict[str, Any],
    subtitles: List[Dict[str, Any]],
    video_duration: float,
    min_duration: float = 8.0,
    max_duration: float = 45.0,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Uses local LLM (or Cognitive Heuristic Engine on standby) to evaluate narrative arc,
    prune stream housekeeping/alerts, snap setup and punchline boundaries, and generate a viral title.
    """
    start_t = float(clip.get("start", 0))
    end_t = float(clip.get("end", 0))
    climax_t = float(clip.get("climax_t", (start_t + end_t) / 2))
    rank_num = int(clip.get("rank", 1))
    reason = str(clip.get("reason", "Highlight"))

    # 1. First run the Cognitive NLP Narrative Evaluation
    arc = evaluate_narrative_micro_arc(subtitles, start_t, end_t, climax_t)
    if arc["is_housekeeping"]:
        clip["is_rejected_by_llm"] = True
        clip["llm_rejection_reason"] = arc["rejection_reason"]
        return clip

    # Boundary refinement: never cut mid-sentence
    dur = arc["duration"]
    if min_duration <= dur <= max_duration:
        clip["start"] = arc["start"]
        clip["end"] = arc["end"]
        clip["duration"] = round(dur, 1)

    clip["llm_punchline"] = arc["summary"]
    clip.setdefault("metrics", {})
    clip["metrics"]["hook_quality"] = arc["hook_score"]
    clip["llm_verified"] = True

    # 2. Curiosity Gap Titling
    synthesized_title = synthesize_curiosity_gap_title(arc["full_speech"], reason, rank=rank_num)
    clip["title"] = f"Rank #{rank_num} • {synthesized_title}"

    # 3. If local Ollama daemon is active, prompt LLM for custom bespoke titling
    if is_ollama_online():
        full_speech = arc['full_speech']
        words = full_speech.split()
        punchline = " ".join(words[max(0, len(words)*2//3):min(len(words), len(words)*2//3 + 10)])
        prompt = f"""Gaming clip title expert. Streamer said:

"{full_speech[:300]}"

Punchline: "{punchline}"

Write ONE viral title that:
- Uses EXACT words/actions from the dialogue (NOT generic filler like "INSANE REACTION")
- ALL-CAPS with 1-2 emojis from: 💀 😭 🔥 🤯
- Under 50 characters

Output ONLY JSON:
{{"viral_title": "DIALOGUE-BASED TITLE 💀", "punchline_summary": "What happened", "hook_score": 92}}"""

        resp_str = query_ollama(prompt, system_prompt="", model=model, timeout=40.0)
        if resp_str:
            try:
                m = re.search(r"\{[\s\S]*\}", resp_str)
                if m:
                    result = json.loads(m.group(0))
                    v_title = result.get("viral_title", "").strip()
                    generic_markers = ["insane reaction", "crazy moment", "wild moment", "stream moment"]
                    is_generic = any(gm in v_title.lower() for gm in generic_markers)
                    if v_title and 5 <= len(v_title) <= 52 and not is_generic:
                        v_title = re.sub(r"^Rank\s*#?\d+\s*•\s*", "", v_title)
                        clip["title"] = f"Rank #{rank_num} • {v_title}"
                    if result.get("punchline_summary"):
                        clip["llm_punchline"] = result.get("punchline_summary")
                    if result.get("hook_score"):
                        clip["metrics"]["hook_quality"] = int(result["hook_score"])
            except Exception as e:
                print(f"[LLM Engine] JSON parse note: {e}")

    return clip

def batch_refine_clips_with_llm(
    clips: List[Dict[str, Any]],
    subtitles: List[Dict[str, Any]],
    video_duration: float,
    min_duration: float = 8.0,
    max_duration: float = 45.0,
    model: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Refines candidate clips sequentially using local LLM with Cognitive NLP standby."""
    refined = []
    for c in clips:
        rc = refine_clip_with_llm(
            clip=dict(c),
            subtitles=subtitles,
            video_duration=video_duration,
            min_duration=min_duration,
            max_duration=max_duration,
            model=model
        )
        if not rc.get("is_rejected_by_llm", False):
            refined.append(rc)

    for idx, c in enumerate(refined):
        c["rank"] = idx + 1
        if "•" in c.get("title", ""):
            parts = c["title"].split("•", 1)
            c["title"] = f"Rank #{idx + 1} •{parts[1]}"

    return refined if refined else clips

# =====================================================================
# Single-Pass Story Curation Engine (Story-First Architecture)
# =====================================================================

def curate_story_clips_from_windows(
    windows: List[Dict[str, Any]],
    video_duration: float,
    target_count: int = 8,
    min_duration: float = 15.0,
    max_duration: float = 50.0,
    model: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], str]:
    """
    SINGLE-PASS STORY CURATION PIPELINE:
    Takes up to 12 candidate stream windows (centered at heatmap peaks, chat velocity spikes,
    or audio outbursts) with timestamped dialogue lines.
    Sends all candidate windows in ONE single /api/chat call to Qwen3:8b.
    Selects top micro-stories with complete narrative arcs (Hook -> Buildup -> Climax/Punchline),
    determines clean boundary timestamps [start_sec, end_sec], and writes high-CTR curiosity-gap titles.
    """
    if not windows:
        return [], "No candidate windows provided."

    max_eval = min(len(windows), 12)
    eval_windows = windows[:max_eval]

    # Cognitive NLP fallback builder in case Ollama is offline or returns invalid output
    def _cognitive_fallback() -> Tuple[List[Dict[str, Any]], str]:
        results = []
        for idx, w in enumerate(eval_windows[:target_count], 1):
            w_id = w.get("window_id", idx)
            center = float(w.get("center_sec", (w.get("start_bound", 0) + w.get("end_bound", 30)) / 2))
            s_bound = float(w.get("start_bound", max(0.0, center - 20.0)))
            e_bound = float(w.get("end_bound", min(video_duration, center + 25.0)))
            
            # Default window ~32s centered near peak
            c_start = max(s_bound, round(center - 10.0, 1))
            c_end = min(e_bound, round(c_start + 32.0, 1))
            if (c_end - c_start) < min_duration:
                c_end = min(video_duration, c_start + min_duration)

            speech_text = w.get("spoken_text") or " ".join(w.get("transcript_lines", []))
            reason = str(w.get("source", "Highlight peak"))
            v_title = synthesize_curiosity_gap_title(speech_text, reason, rank=idx)

            results.append({
                "window_id": w_id,
                "rank": idx,
                "title": f"Rank #{idx} • {v_title}",
                "start": round(c_start, 1),
                "end": round(c_end, 1),
                "duration": round(c_end - c_start, 1),
                "climax_t": round(center, 1),
                "virality_score": int(min(99, max(80, int(w.get("peak_score", 85))))),
                "reason": f"⚡ Story-First Climax ({w.get('source', 'Peak')})",
                "badge_color": "#EF4444" if idx <= 2 else "#F59E0B",
                "ai_curated": True,
                "llm_verified": False,
                "llm_punchline": "Micro-story arc curated via Cognitive NLP standby"
            })
        return results, "Curated by Cognitive NLP Standby Engine"

    if not is_ollama_online():
        print("[LLM Engine] Ollama offline. Executing Cognitive NLP story curation.")
        return _cognitive_fallback()

    # Format candidate windows for single-pass prompt
    window_blocks = []
    for w in eval_windows:
        wid = w.get("window_id", 1)
        src = w.get("source", "peak")
        center = float(w.get("center_sec", 0.0))
        peak_score = int(w.get("peak_score", 85))
        s_bound = float(w.get("start_bound", max(0.0, center - 25.0)))
        e_bound = float(w.get("end_bound", min(video_duration, center + 30.0)))
        
        lines = w.get("transcript_lines") or []
        if not lines and w.get("spoken_text"):
            lines = [f"[{center:.1f}s] {w.get('spoken_text')}"]
        
        preview_text = "\n".join(lines[:12]) if lines else "[No transcript available - acoustic reaction only]"
        if len(preview_text) > 600:
            preview_text = preview_text[:600] + "..."

        block = (
            f"--- WINDOW #{wid} (Source: {src}, Peak at {center:.1f}s, Excitement {peak_score}%) ---\n"
            f"Allowed Range: {s_bound:.1f}s to {e_bound:.1f}s\n"
            f"Transcript:\n{preview_text}"
        )
        window_blocks.append(block)

    windows_text = "\n\n".join(window_blocks)

    system_prompt = (
        "You are an Elite Executive Producer for YouTube Shorts & TikTok. "
        "Your mission is to discover self-contained viral micro-stories from live stream candidate windows. "
        "A viral short MUST have: "
        "1. Hook Onset (first 2-3s): Gripping opening statement, unexpected question, or sudden event. "
        "2. Escalation / Context: Building tension, banter, or gameplay action. "
        "3. Climax & Punchline: Instant funny or shocking payoff. "
        "REJECT housekeeping, stream tech setup, mundane silence, or sub/donation alerts."
    )

    user_prompt = f"""Review these {len(eval_windows)} candidate highlight windows from a stream ({int(video_duration//60)} mins total):

{windows_text}

SELECT up to {target_count} moments that form the most captivating micro-stories.
For each chosen clip:
1. Specify exact "start_sec" and "end_sec" within that window's Allowed Range.
2. Clip duration MUST be between {int(min_duration)}s and {int(max_duration)}s.
3. Write an ALL-CAPS curiosity-gap "viral_title" that references SPECIFIC dialogue words or actions (NOT generic like "INSANE MOMENT"). Add 1-2 emojis (💀 😭 🔥 🤯 😱 🚔 🏎️).
4. Provide a brief 1-sentence "punchline_summary".

Respond ONLY in valid JSON matching this schema:
{{
  "clips": [
    {{
      "window_id": 1,
      "start_sec": 124.5,
      "end_sec": 156.0,
      "viral_title": "HE GAVE $20,000 TO A HOMELESS NPC 😭❤️",
      "punchline_summary": "Streamer gives all his cash to an NPC who roasts him back.",
      "hook_score": 94,
      "virality_score": 96
    }}
  ],
  "editorial_reason": "High emotional engagement with strong punchlines and dialogue hooks."
}}"""

    chosen_model = model or get_preferred_llama_model()
    resp_text = query_ollama(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=chosen_model,
        timeout=120.0,
        num_predict=1400,
        json_mode=True
    )

    if not resp_text:
        print("[LLM Engine] Single-pass story curation received no response, using fallback.")
        return _cognitive_fallback()

    try:
        m = re.search(r"\{[\s\S]*\}", resp_text)
        if not m:
            return _cognitive_fallback()

        parsed = json.loads(m.group(0))
        raw_clips = parsed.get("clips", [])
        editorial_reason = parsed.get("editorial_reason", "Curated by Qwen3 Story Mind")

        if not raw_clips or not isinstance(raw_clips, list):
            return _cognitive_fallback()

        window_map = {w.get("window_id", idx + 1): w for idx, w in enumerate(eval_windows)}
        selected_clips = []
        seen_intervals = []

        def _is_overlap(s: float, e: float) -> bool:
            for os, oe in seen_intervals:
                if max(s, os) < min(e, oe):
                    overlap = min(e, oe) - max(s, os)
                    if (overlap / max(1.0, e - s)) > 0.35 or (overlap / max(1.0, oe - os)) > 0.35:
                        return True
            return False

        for item in raw_clips:
            wid = item.get("window_id")
            w_orig = window_map.get(wid) or window_map.get(str(wid)) or (eval_windows[0] if eval_windows else {})
            
            s_val = float(item.get("start_sec") or w_orig.get("start_bound", 0.0))
            e_val = float(item.get("end_sec") or (s_val + 32.0))

            # Clamp boundaries
            s_val = max(0.0, min(video_duration - min_duration, s_val))
            dur = e_val - s_val
            if dur < min_duration:
                e_val = min(video_duration, s_val + min_duration)
            elif dur > max_duration:
                e_val = min(video_duration, s_val + max_duration)
            dur = e_val - s_val

            if _is_overlap(s_val, e_val):
                continue
            seen_intervals.append((s_val, e_val))

            rank_idx = len(selected_clips) + 1
            v_title = str(item.get("viral_title", "")).strip()
            if not v_title or len(v_title) < 5 or any(g in v_title.lower() for g in ["insane reaction", "crazy moment"]):
                speech_text = w_orig.get("spoken_text") or " ".join(w_orig.get("transcript_lines", []))
                v_title = synthesize_curiosity_gap_title(speech_text, str(w_orig.get("source", "peak")), rank=rank_idx)
            v_title = re.sub(r"^Rank\s*#?\d+\s*•\s*", "", v_title)

            base_virality = int(item.get("virality_score") or w_orig.get("peak_score", 88))
            virality = min(99, max(75, base_virality + 3))

            selected_clips.append({
                "window_id": wid,
                "rank": rank_idx,
                "title": f"Rank #{rank_idx} • {v_title}",
                "start": round(s_val, 1),
                "end": round(e_val, 1),
                "duration": round(dur, 1),
                "climax_t": round(float(w_orig.get("center_sec", (s_val + e_val) / 2)), 1),
                "virality_score": virality,
                "reason": f"⚡ Story-First Micro-Arc ({w_orig.get('source', 'Peak')})",
                "badge_color": "#EF4444" if rank_idx <= 2 else "#F59E0B",
                "ai_curated": True,
                "llm_verified": True,
                "llm_punchline": item.get("punchline_summary") or editorial_reason,
                "metrics": {
                    "hook_quality": int(item.get("hook_score", 90)),
                    "voice_energy": int(w_orig.get("peak_score", 85)),
                    "story_arc": 95
                }
            })

            if len(selected_clips) >= target_count:
                break

        if selected_clips:
            print(f"[LLM Engine] Single-Pass Story Curation succeeded with {len(selected_clips)} clips on model {chosen_model}")
            return selected_clips, editorial_reason

    except Exception as parse_err:
        print(f"[LLM Engine] Failed parsing story curation JSON: {parse_err}")

    return _cognitive_fallback()

def curate_auto_viral_clips(
    candidates: List[Dict[str, Any]],
    subtitles: List[Dict[str, Any]],
    video_duration: float,
    target_count: Optional[int] = None,
    min_duration: float = 12.0,
    max_duration: float = 45.0,
    model: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    LLM Story-First Executive Producer:
    Reviews candidate moments from multimodal sensory detection.
    Prepares candidate windows with timestamped subtitle dialogue and invokes
    curate_story_clips_from_windows in a single-pass request to Qwen3:8b.
    """
    if not candidates:
        return [], None

    target_n = target_count or max(3, min(12, int(video_duration / 250)))

    # Convert candidates into story windows with timestamped dialogue
    windows = []
    for idx, c in enumerate(candidates[:max(target_n + 4, 12)], 1):
        c_start = float(c.get("start", 0))
        c_end = float(c.get("end", 0))
        climax_t = float(c.get("climax_t", (c_start + c_end) / 2))

        # Gather timestamped lines within window
        matching_subs = [
            s for s in (subtitles or [])
            if float(s.get("end", 0)) >= max(0.0, climax_t - 14.0) and float(s.get("start", 0)) <= min(video_duration, climax_t + 20.0)
        ]
        t_lines = []
        for s in matching_subs[:10]:
            txt = s.get("text", "").strip()
            if txt:
                t_lines.append(f"[{float(s.get('start', 0)):.1f}s] {txt}")

        spoken_text = " ".join(s.get("text", "").strip() for s in matching_subs)
        windows.append({
            "window_id": idx,
            "source": c.get("reaction_category", "Audio Peak"),
            "peak_score": int(c.get("virality_score", 85)),
            "center_sec": climax_t,
            "start_bound": max(0.0, c_start - 4.0),
            "end_bound": min(video_duration, c_end + 4.0),
            "transcript_lines": t_lines,
            "spoken_text": spoken_text,
            "orig_cand": c
        })

    curated_clips, reason = curate_story_clips_from_windows(
        windows=windows,
        video_duration=video_duration,
        target_count=target_n,
        min_duration=min_duration,
        max_duration=max_duration,
        model=model
    )

    # Re-merge original candidate sensory metrics into curated clips
    final_clips = []
    window_cand_map = {w["window_id"]: w["orig_cand"] for w in windows}

    for clip in curated_clips:
        raw_wid = clip.get("window_id")
        orig = None
        # Safely normalize wid (int(wid) with try/except) so string IDs like "1" match integer keys
        norm_wid = None
        try:
            if raw_wid is not None:
                norm_wid = int(raw_wid)
        except (ValueError, TypeError):
            norm_wid = None

        if norm_wid is not None and norm_wid in window_cand_map:
            orig = window_cand_map[norm_wid]
        elif raw_wid in window_cand_map:
            orig = window_cand_map[raw_wid]
        else:
            # Fall back to the nearest overlapping candidate by timestamp if wid is still unmatched
            c_start = float(clip.get("start", 0.0))
            c_end = float(clip.get("end", c_start + 15.0))
            c_mid = (c_start + c_end) / 2.0
            best_cand = None
            min_dist = float("inf")
            for w in windows:
                w_cand = w.get("orig_cand")
                if not w_cand:
                    continue
                w_mid = (float(w_cand.get("start", 0.0)) + float(w_cand.get("end", 0.0))) / 2.0
                dist = abs(c_mid - w_mid)
                if dist < min_dist:
                    min_dist = dist
                    best_cand = w_cand
            orig = best_cand

        if orig:
            merged = dict(orig)
            merged.update(clip)
            final_clips.append(merged)
        else:
            final_clips.append(clip)

    return final_clips if final_clips else candidates[:target_n], reason
