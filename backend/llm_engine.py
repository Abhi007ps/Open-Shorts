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
    Selects the best available local LLM model for viral clip titling.
    On CPU-based local setups, prioritizes ultra-fast lightweight models (qwen2.5:0.5b / qwen2.5:1.5b / llama3.2:1b)
    to guarantee snappy 2-4 second inference without timeouts or CPU stalls.
    """
    installed = get_installed_llm_models()
    if not installed:
        return None

    priority = [
        "qwen2.5:0.5b",
        "qwen2.5:1.5b",
        "llama3.2:1b",
        "llama3.2:latest",
        "qwen2.5:3b",
        "qwen3.5:4b",
        "llama3.2:3b",
        "llama3.1:8b",
        "llama3.1:latest",
        "llama3.1",
        "llama3.2",
        "mistral:7b"
    ]
    for p in priority:
        for m in installed:
            if m == p or m.startswith(p):
                return m

    return installed[0] if installed else None

def query_ollama(prompt: str, system_prompt: str = "", model: Optional[str] = None, timeout: float = 60.0) -> Optional[str]:
    """Sends an inference request to Ollama with low temperature for deterministic JSON output."""
    chosen_model = model or get_preferred_llama_model()
    if not chosen_model:
        return None

    url = f"{OLLAMA_BASE_URL}/api/generate"
    # qwen3.5:4b can handle larger contexts; give it room for better titles
    is_large_model = any(tag in chosen_model for tag in ["qwen3.5", "qwen2.5:7b", "llama3.1:8b", "llama3.2:3b", "mistral:7b"])
    payload = {
        "model": chosen_model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 150 if is_large_model else 90,
            "num_ctx": 2048 if is_large_model else 1024
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        print(f"[LLM Engine] Ollama generation failed: {e}")
        return None

# =====================================================================
# Professional Clipper Cognitive NLP Engine (Opus Clip / Klap Standard)
# =====================================================================

VIRAL_ENTITY_CATEGORIES = {
    "homeless_kindness": {
        "keywords": ["homeless", "beggar", "money", "20000", "20,000", "20k", "thousand", "dollars", "cash", "give him", "donate", "poor", "rich", "kindness"],
        "titles": [
            "HE GAVE $20,000 TO A HOMELESS NPC 😭❤️",
            "STREAMER SHOWS CRAZY KINDNESS IN GTA 6 🥺❤️",
            "HE GAVE ALL HIS MONEY TO THIS NPC 😭🔥",
            "BRO HELPED A HOMELESS NPC AND THIS HAPPENED 🥺💀",
            "THIS IS WHY EVERYONE LOVES THIS STREAMER 🥺❤️"
        ]
    },
    "backflip_stunt": {
        "keywords": ["backflip", "flip", "stunt", "jump", "parkour", "roof", "trick", "first streamer", "physics", "first person to"],
        "titles": [
            "FIRST STREAMER TO DO A BACKFLIP IN GTA 6?! 💀🔥",
            "BRO TRIED A BACKFLIP AND THIS HAPPENED 😭💀",
            "THE MOST INSANE STUNT IN GTA 6 HISTORY 🤯🔥",
            "NO WAY HE PULLED OFF THIS BACKFLIP 💀🏆",
            "PHYSICS IN GTA 6 ARE ACTUALLY BROKEN 😭🔥"
        ]
    },
    "npc_bizarre": {
        "keywords": ["peeing", "pee", "piss", "pitch this much", "bathroom", "toilet", "wall", "weirdest npc", "npc doing", "caught npc", "strange npc", "urinat", "wash his hand", "wash his hands", "watch his hand", "tank you got"],
        "titles": [
            "CAUGHT AN NPC DOING THIS IN GTA 6 💀😭",
            "BRO FOUND THE WEIRDEST NPC IN GTA 6 😭💀",
            "HE CAUGHT THIS NPC IN 4K 💀📸",
            "THIS GTA 6 NPC HAS NO SHAME 😭💀",
            "I CANNOT BELIEVE ROCKSTAR ADDED THIS NPC 💀"
        ]
    },
    "animal_wildlife": {
        "keywords": ["chameleon", "lizard", "reptile", "roadkill", "alligator", "gator", "crocodile", "dog", "cat", "animal", "snake", "creature"],
        "titles": [
            "BRO ENCOUNTERED A ROADKILL CHAMELEON 😭💀",
            "HE FOUND THE RAREST ANIMAL IN GTA 6 💀🦎",
            "BRO COULD NOT BELIEVE THIS ANIMAL IN GTA 6 😭",
            "GTA 6 WILDLIFE IS ACTUALLY OUT OF CONTROL 💀🔥",
            "HE ACCIDENTALLY RAN OVER THIS IN GTA 6 💀😭"
        ]
    },
    "police_chase": {
        "keywords": ["police", "cop", "cops", "5 star", "5-star", "five star", "wanted", "busted", "siren", "chase", "swat", "arrested", "prison", "jail"],
        "titles": [
            "5-STAR WANTED LEVEL ESCAPE GONE WRONG 💀🚔",
            "BRO TRIED TO ESCAPE THE COPS IN GTA 6 😭🚔",
            "HE GOT 5 STARS IN 10 SECONDS 💀🚨",
            "THE POLICE DID NOT LET THAT SLIDE 💀🚔",
            "FASTEST 5-STAR BUSTED IN GTA 6 HISTORY 😭💀"
        ]
    },
    "car_crash": {
        "keywords": ["car", "ferrari", "lambo", "lamborghini", "sports car", "supercar", "crash", "crashed", "driving", "drift", "engine", "vehicle", "wrecked", "speeding"],
        "titles": [
            "BRO CRASHED A SUPERCAR IN GTA 6 💀🏎️",
            "DRIVING AT MAX SPEED IN GTA 6 GONE WRONG 😭🔥",
            "BRO COMPLETELY TOTALED HIS CAR 💀😭",
            "THE MOST EXPENSIVE CAR CRASH IN GTA 6 💀🏎️",
            "HE TESTED GTA 6 CAR CRASH PHYSICS 🤯💀"
        ]
    },
    "grandma_npc": {
        "keywords": ["grandma", "grandpa", "old lady", "old woman", "elderly", "granny"],
        "titles": [
            "BRO RAN INTO A GTA 6 GRANDMA 💀😭",
            "THIS GTA 6 GRANDMA IS DANGEROUS 😭💀",
            "HE REALLY FOUGHT A GRANDMA ON STREAM 💀",
            "GTA 6 GRANDMA SHOWED HIM WHO IS BOSS 😭💀"
        ]
    },
    "glitch_easter_egg": {
        "keywords": ["glitch", "bug", "broken", "flying", "through floor", "easter egg", "secret", "hidden", "unreal", "teleport"],
        "titles": [
            "BRO FOUND A GAME-BREAKING GLITCH IN GTA 6 🤯💀",
            "GTA 6 PHYSICS BROKE COMPLETELY 😭💀",
            "HE DISCOVERED A SECRET EASTER EGG IN GTA 6 🤫🔥",
            "THIS GTA 6 GLITCH IS ACTUALLY INSANE 💀"
        ]
    },
    "npc_dialogue": {
        "keywords": ["flat ass", "stick up", "get out", "back off", "leave me alone", "what are you doing", "stop following me", "you're crazy"],
        "titles": [
            "GTA 6 NPC SAID WHAT 💀🤣",
            "BRO THIS NPC HAS NO FILTER 💀😭",
            "GTA 6 NPC ROASTED HIM IN 4K 😭💀",
            "ROCKSTAR REALLY ADDED THIS NPC DIALOGUE 💀"
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
            "HE FOUND SOMETHING INSANE IN GTA 6 💀🔥",
            "BRO DISCOVERED THIS HIDDEN DETAIL 🤯💀",
            "NOBODY NOTICED THIS IN GTA 6 💀",
            "GTA 6 DETAIL THAT BREAKS YOUR BRAIN 😭🔥"
        ]
    },
    "money_spending": {
        "keywords": ["buy", "bought", "spend", "spent", "cost", "price", "expensive", "million", "billion", "thousand", "dollar", "money", "cash", "pay"],
        "titles": [
            "HE SPENT HOW MUCH ON THIS IN GTA 6?! 💀😭",
            "BRO WENT COMPLETELY BROKE IN GTA 6 😭💀",
            "THE MOST EXPENSIVE PURCHASE IN GTA 6 💀🤑",
            "THIS IS WHY HE HAS NO MONEY IN GTA 6 😭🔥"
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
        # Snap start to first spoken word near start_t with -40ms vocal attack lead
        first_sub_start = float(matching_subs[0].get("start", start_t))
        if abs(first_sub_start - start_t) <= 3.0:
            hook_word_start = max(0.0, first_sub_start - 0.04)

        # Snap end to final spoken word punchline (+0.35s reaction snap)
        last_sub_end = float(matching_subs[-1].get("end", end_t))
        if last_sub_end > climax_t and (last_sub_end - climax_t) <= 6.0:
            punchline_end = last_sub_end + 0.35

        for s in matching_subs:
            txt = s.get("text", "").strip()
            if txt:
                spoken_phrases.append(txt)

    full_speech = " ".join(spoken_phrases)

    # Check for stream housekeeping rejection
    is_housekeeping = False
    rejection_reason = None
    for pattern in HOUSEKEEPING_PATTERNS:
        if re.search(pattern, full_speech, re.IGNORECASE):
            is_housekeeping = True
            rejection_reason = f"Filtered mundane stream housekeeping ({pattern})"
            break

    # Retention hook quality calculation (0-100)
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
    Uses local Llama 3.2 (or Cognitive Heuristic Engine on standby) to evaluate narrative arc,
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
        # Extract punchline (last third = climax/punchline)
        words = full_speech.split()
        punchline = " ".join(words[max(0, len(words)*2//3):min(len(words), len(words)*2//3 + 10)])
        prompt = f"""Gaming clip title expert. Streamer said:

"{full_speech[:300]}"

Punchline: "{punchline}"

Write ONE viral title that:
- Uses EXACT words/actions from the dialogue (NOT "INSANE REACTION" or generic filler)
- ALL-CAPS with 1-2 emojis from: 💀 😭 🔥 🤯
- Under 50 characters

Output ONLY JSON:
{{"viral_title": "DIALOGUE-BASED TITLE 💀", "punchline_summary": "What happened", "hook_score": 92}}"""

        resp_str = query_ollama(prompt, system_prompt="", model=model, timeout=60.0)
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
    """Refines candidate clips sequentially using local Llama 3.2 with Cognitive NLP standby."""
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
        # Update title rank prefix if present
        if "•" in c.get("title", ""):
            parts = c["title"].split("•", 1)
            c["title"] = f"Rank #{idx + 1} •{parts[1]}"

    return refined if refined else clips

def curate_auto_viral_clips(
    candidates: List[Dict[str, Any]],
    subtitles: List[Dict[str, Any]],
    video_duration: float,
    target_count: Optional[int] = None,
    model: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    LLM Unified Mind Executive Producer:
    Reviews candidate moments from multimodal sensory detection.
    Evaluates dialogue, emotional climax, streamer interaction, and retention potential
    to decide the optimal number of insane-virality clips that should be produced.
    Prunes lukewarm filler and returns moments with true viral payoff and active streamer reaction.
    """
    if not candidates:
        return [], None

    target_n = target_count or max(3, min(14, int(video_duration / 250)))

    # If Ollama is offline or standby, execute Cognitive NLP heuristic curation
    if not is_ollama_online():
        print("[LLM Engine] Ollama standby mode active. Running Cognitive NLP Curation Engine.")
        approved_clips = []
        for idx, c in enumerate(candidates[:max(target_n + 3, 10)], 1):
            cloned = dict(c)
            cloned["rank"] = idx
            refined = refine_clip_with_llm(cloned, subtitles, video_duration, model=model)
            if not refined.get("is_rejected_by_llm", False):
                refined["ai_curated"] = True
                refined["virality_score"] = min(99, refined.get("virality_score", 80) + 6)
                approved_clips.append(refined)
                if len(approved_clips) >= target_n:
                    break

        if not approved_clips and candidates:
            approved_clips = candidates[:min(target_n, len(candidates))]

        reason = "Cognitive NLP Curated (Curiosity Gaps & Micro-Arc Retention)"
        return approved_clips, reason

    chosen_model = model or get_preferred_llama_model()
    if not chosen_model:
        return candidates[:min(target_n, len(candidates))], "Default sensory ranking"

    eval_candidates = candidates[:min(len(candidates), max(10, target_n + 5))]

    lines = []
    for idx, c in enumerate(eval_candidates, 1):
        c_start = float(c.get("start", 0))
        c_end = float(c.get("end", 0))
        climax_t = float(c.get("climax_t", (c_start + c_end) / 2))
        
        c_subs = [
            s.get("text", "").strip() for s in subtitles
            if float(s.get("end", 0)) >= max(0.0, climax_t - 6.0) and float(s.get("start", 0)) <= min(video_duration, climax_t + 6.0)
        ]
        clean_speech = " ".join([txt for txt in c_subs if txt][:4])
        if not clean_speech:
            clean_speech = "[Intense non-verbal vocal reaction & gameplay action]"

        v_score = int(c.get("virality_score", 80))
        lines.append(f"Candidate #{idx} (Peak at {climax_t:.1f}s, Excitement {v_score}%): \"{clean_speech[:95]}\"")

    cand_text = "\n".join(lines)
    stream_mins = max(1, int(video_duration / 60))
    prompt = f"""Review these {len(eval_candidates)} livestream highlight moments from a {stream_mins}-minute gaming stream:
{cand_text}

You are the Executive Producer for YouTube Shorts & TikTok.
Select the top {target_n} moments with intense streamer reactions (screams, laughter, anger, clutch plays, or funny fails).
REJECT moments where the streamer is quietly playing or doing boring housekeeping.
CRITICAL: Include specific entities, subjects or actions from the dialogue in the viral titles (e.g., Homeless, Backflip, Peeing NPC, Chameleon, 5-Star Cops, Crash, Supercar).
Respond in JSON format:
{{"selected_candidate_ids": [1, 2, 3, 4], "viral_titles": {{"1": "HE GAVE $20,000 TO A HOMELESS NPC 😭❤️", "2": "FIRST STREAMER TO DO A BACKFLIP IN GTA 6?! 💀🔥"}}, "editorial_reason": "High emotional streamer reactions and funny commentary."}}"""

    payload = {
        "model": chosen_model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 120,
            "num_ctx": 1024
        }
    }

    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=75.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw = data.get("response", "").strip()

        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            result = json.loads(m.group(0))
            selected_ids = result.get("selected_candidate_ids", [])
            titles = result.get("viral_titles", {})
            reason = result.get("editorial_reason", "Curated by Llama 3.2 Unified Mind")

            int_ids = []
            for sid in selected_ids:
                try:
                    int_ids.append(int(sid))
                except Exception:
                    pass

            approved_clips = []
            for cid in int_ids:
                if 1 <= cid <= len(eval_candidates):
                    cand = eval_candidates[cid - 1]
                    cand["llm_verified"] = True
                    cand["ai_curated"] = True
                    cand["llm_punchline"] = reason
                    c_title = titles.get(str(cid)) or titles.get(cid)
                    if c_title and len(c_title) <= 45:
                        c_title = re.sub(r"^Rank\s*#?\d+\s*•\s*", "", c_title)
                        cand["title"] = f"Rank #{len(approved_clips)+1} • {c_title}"
                    cand["virality_score"] = min(99, cand.get("virality_score", 80) + 7)
                    approved_clips.append(cand)

            if approved_clips:
                return approved_clips, reason

    except Exception as e:
        print(f"[LLM Mind] Auto-curation error: {e}")

    # Fallback to Cognitive NLP curation
    fallback = []
    for idx, c in enumerate(candidates[:target_n], 1):
        cloned = dict(c)
        cloned["rank"] = idx
        refined = refine_clip_with_llm(cloned, subtitles, video_duration, model=model)
        fallback.append(refined)
    return fallback, "Cognitive NLP Multimodal Peak Ranking (LLM Standby)"
