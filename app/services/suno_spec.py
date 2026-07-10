import re
from typing import Any

from app.models import Song


LANGUAGE_LABELS = ["Mandarin", "Chinese", "普通话", "中文", "language-focused", "literary synopsis"]


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def strip_language_labels(value: str | None) -> tuple[str, bool]:
    text = _clean_text(value)
    changed = False
    for label in LANGUAGE_LABELS:
        if re.search(re.escape(label), text, flags=re.IGNORECASE):
            text = re.sub(re.escape(label), "", text, flags=re.IGNORECASE)
            changed = True
    return _clean_text(text), changed


def _split_genres(genre_direction: str | None) -> tuple[str, str, bool]:
    cleaned, filtered = strip_language_labels(genre_direction)
    if not cleaned:
        return "intimate alternative pop", "lo-fi electronic texture", filtered
    parts = [part.strip(" -") for part in re.split(r"[/,;|+]+", cleaned) if part.strip(" -")]
    primary = parts[0] if parts else "intimate alternative pop"
    secondary = parts[1] if len(parts) > 1 else "minimal electronic texture"
    return primary, secondary, filtered


def _tempo_feel(bpm: int) -> str:
    if bpm < 76:
        return "slow, spacious pulse"
    if bpm < 96:
        return "restrained mid-tempo pocket"
    if bpm < 122:
        return "forward mid-tempo drive"
    return "fast, urgent motion"


def _infer_mood(emotional_goal: str) -> str:
    text = emotional_goal.lower()
    if any(term in text for term in ["angry", "rage", "sharp", "冲", "怒"]):
        return "tense, clipped, unresolved"
    if any(term in text for term in ["sweet", "warm", "温柔", "甜"]):
        return "warm but restrained"
    if any(term in text for term in ["cold", "lonely", "失眠", "旧", "access", "denied"]):
        return "cold, intimate, unresolved"
    return "intimate, controlled, emotionally specific"


def _infer_vocal_delivery(emotional_goal: str) -> str:
    text = emotional_goal.lower()
    if any(term in text for term in ["breath", "呼吸", "低电", "tired"]):
        return "close, breath-aware, lightly tired consonants"
    if any(term in text for term in ["angry", "rage", "sharp", "怒"]):
        return "controlled edge, clipped phrases, no shouting"
    return "close, restrained, clear diction"


def _infer_mix_space(emotional_goal: str) -> str:
    text = emotional_goal.lower()
    if any(term in text for term in ["room", "bedroom", "卧室", "night", "夜"]):
        return "dry lead in a small room with short ambience"
    if any(term in text for term in ["wide", "cinematic", "大"]):
        return "medium-wide pads with dry vocal center"
    return "dry vocal center, narrow intimate space"


def _list_from_artifact(accepted_artifacts: list[Any] | None, artifact_type: str, key: str) -> str:
    for artifact in accepted_artifacts or []:
        if getattr(artifact, "artifact_type", None) != artifact_type:
            continue
        content = getattr(artifact, "content", {}) or {}
        value = content.get(key)
        if value:
            return str(value)
    return ""


def normalize_song_to_music_spec(
    song: Song,
    accepted_artifacts: list[Any] | None = None,
    feedback_summary: dict | None = None,
) -> dict:
    feedback_summary = feedback_summary or {}
    primary, secondary, genre_filtered = _split_genres(song.genre_direction)
    emotional_goal, emotional_filtered = strip_language_labels(song.emotional_goal)
    bpm = int(song.bpm or 92)
    source_notes = []
    if genre_filtered or emotional_filtered:
        source_notes.append("language_label_filtered")
    if song.language_plan:
        source_notes.append(f"language_plan available for lyrics/package metadata: {song.language_plan}")

    recurring = set(feedback_summary.get("recurring_problems") or [])
    blocked = set(feedback_summary.get("blocked_terms") or [])

    vocal_delivery = _infer_vocal_delivery(emotional_goal)
    rhythm_groove = "restrained drums with a clear backbeat and light syncopation"
    production_texture = ["muted keys", "narrow synth pad", "small tactile motif"]

    if "heavy_drums" in recurring or "heavy drums" in blocked:
        rhythm_groove = "drums softened, reduced percussion density, clear dry pulse"
        production_texture.append("softened transient layer")
    if "over_sweet_vocal" in recurring or "too sweet vocal" in blocked:
        vocal_delivery = "less sweet, more restrained vocal with clear diction"
        production_texture.append("less glossy vocal treatment")
    if "style_drift" in recurring:
        production_texture.append("tighter genre and instrument palette")

    return {
        "use_case": song.function_in_ep or "EP production prompt pack",
        "language_plan": song.language_plan or "",
        "primary_genre": primary,
        "secondary_genre": secondary,
        "mood": _infer_mood(emotional_goal),
        "bpm": bpm,
        "tempo_feel": _tempo_feel(bpm),
        "vocal_type": "lead vocal with restrained doubles",
        "vocal_delivery": vocal_delivery,
        "instrumentation": ["dry kick", "soft snare", "sub bass", "muted electric piano", "narrow synth pad"],
        "rhythm_groove": rhythm_groove,
        "bass_behavior": "warm low-end pressure answering the hook with a simple pattern",
        "harmony_palette": ["minor color", "suspended passing chords", "simple loop anchor"],
        "production_texture": production_texture,
        "mix_space": _infer_mix_space(emotional_goal),
        "energy_curve": "small verse, clearer chorus, stripped bridge, restrained final return",
        "commercial_safety": True,
        "source_notes": source_notes,
        "accepted_hook": _list_from_artifact(accepted_artifacts, "hook_set", "recommended_hook") or song.locked_hook,
        "accepted_lyrics_available": bool(song.lyrics.strip()),
    }
