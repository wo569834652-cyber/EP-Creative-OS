import re

from app.services.suno_spec import LANGUAGE_LABELS


ARTIST_REFERENCE_TERMS = [
    "Taylor Swift",
    "Billie Eilish",
    "The Weeknd",
    "Drake",
    "BTS",
    "Disney",
    "Marvel",
]


def _result(score: int, passed: list[str], warnings: list[str], blocking: list[str]) -> dict:
    if blocking:
        score = min(score, 68)
    return {
        "score": max(0, min(100, int(score))),
        "passed_checks": passed,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(re.search(re.escape(term), text, flags=re.IGNORECASE) for term in terms)


def _add_check(condition: bool, label: str, passed: list[str], warnings: list[str], blocking: list[str], block: bool = False) -> int:
    if condition:
        passed.append(label)
        return 0
    if block:
        blocking.append(label)
        return 12
    warnings.append(label)
    return 7


def validate_style_prompt(style_prompt: str, music_spec: dict) -> dict:
    text = style_prompt or ""
    lower = text.lower()
    passed: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    penalty = 0

    checks = [
        (music_spec.get("primary_genre", "").lower() in lower, "primary genre present", True),
        (
            music_spec.get("secondary_genre", "").lower() in lower or "texture" in lower or "palette" in lower,
            "secondary genre or explicit texture present",
            False,
        ),
        (f"{music_spec.get('bpm')} BPM" in text or "BPM" in text, "BPM present", True),
        ("vocal" in lower and ("direction" in lower or "delivery" in lower), "vocal direction present", True),
        (any(str(item).lower() in lower for item in music_spec.get("instrumentation", [])), "instrumentation present", True),
        (any(term in lower for term in ["groove", "drums", "rhythm", "pulse"]), "groove/drums/rhythm present", True),
        (any(term in lower for term in ["bass", "low-end", "sub"]), "bass or low-end present", True),
        (any(term in lower for term in ["mix", "space", "room"]), "mix/space present", True),
    ]
    for condition, label, block in checks:
        penalty += _add_check(condition, label, passed, warnings, blocking, block)

    language_pollution = _contains_any(text, LANGUAGE_LABELS)
    penalty += _add_check(not language_pollution, "style prompt has no language labels", passed, warnings, blocking, True)
    if "language_label_filtered" in (music_spec.get("source_notes") or []):
        warnings.append("language labels were filtered from song inputs before style prompt composition")
        penalty += 4

    penalty += _add_check(not _contains_any(text, ARTIST_REFERENCE_TERMS), "no artist/brand/copyright-style reference", passed, warnings, blocking, True)
    negative_leak = bool(re.search(r"\b(no|avoid|forbidden)\b", lower))
    penalty += _add_check(not negative_leak, "style prompt keeps negative controls out of style text", passed, warnings, blocking, True)
    abstract_terms = sum(1 for term in ["vibe", "feeling", "essence", "dream", "soul", "destiny"] if term in lower)
    penalty += _add_check(abstract_terms <= 2, "not overly abstract", passed, warnings, blocking, False)
    penalty += _add_check(180 <= len(text) <= 1500, "length controlled", passed, warnings, blocking, False)
    return _result(100 - penalty, passed, warnings, blocking)


def validate_lyrics_prompt(lyrics_prompt: str, hook: str, route_spec: dict) -> dict:
    text = lyrics_prompt or ""
    lower = text.lower()
    passed: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    penalty = 0
    has_labels = bool(re.search(r"^\[[^\]]+\]", text, flags=re.MULTILINE))
    penalty += _add_check(has_labels, "section labels present", passed, warnings, blocking, True)
    penalty += _add_check(bool(hook and hook in text), "hook appears in lyrics prompt", passed, warnings, blocking, True)

    chorus_blocks = re.findall(r"\[(?:chorus|hook)[^\]]*\](.*?)(?=\n\[[^\]]+\]|\Z)", text, flags=re.IGNORECASE | re.DOTALL)
    long_chorus = any(len(block.strip()) > 650 for block in chorus_blocks)
    penalty += _add_check(not long_chorus, "chorus/hook instruction length controlled", passed, warnings, blocking, False)
    style_leak = any(term in lower for term in ["primary genre", "secondary genre", "mix/space:", "groove/drums:", "style prompt"])
    penalty += _add_check(not style_leak, "lyrics prompt does not mix in style prompt", passed, warnings, blocking, True)
    control_prose = any(term in lower for term in ["purpose:", "delivery:", "hook control:", "temporary writing scaffold", "revision target"])
    penalty += _add_check(not control_prose, "lyrics prompt avoids control prose", passed, warnings, blocking, True)
    penalty += _add_check(len(text.strip()) >= 40, "lyrics body is present", passed, warnings, blocking, True)

    route_labels = [item.get("label") for item in route_spec.get("section_map", []) if item.get("label")]
    if route_labels:
        penalty += _add_check(any(label in text for label in route_labels), "route section map represented", passed, warnings, blocking, False)
    return _result(100 - penalty, passed, warnings, blocking)


def validate_exclude_prompt(exclude_prompt: str, style_prompt: str) -> dict:
    text = exclude_prompt or ""
    lower = text.lower()
    style_lower = (style_prompt or "").lower()
    passed: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    penalty = 0
    penalty += _add_check(bool(text.strip()), "exclude prompt exists independently", passed, warnings, blocking, True)
    penalty += _add_check(any(term in lower for term in ["drums", "vocal", "reverb", "bass", "drop", "spoken", "percussion", "melody"]), "exclude prompt is concrete and musical", passed, warnings, blocking, True)
    conflicts = ["no drums" in lower and "drums" in style_lower, "no vocal" in lower and "vocal" in style_lower, "no bass" in lower and "bass" in style_lower]
    penalty += _add_check(not any(conflicts), "exclude prompt does not directly conflict with target style", passed, warnings, blocking, True)
    penalty += _add_check("bad quality" not in lower and "make it good" not in lower, "exclude prompt avoids generic bad quality wording", passed, warnings, blocking, False)
    return _result(100 - penalty, passed, warnings, blocking)


def merge_validations(*validations: dict) -> dict:
    if not validations:
        return _result(0, [], [], ["missing validation"])
    score = round(sum(item.get("score", 0) for item in validations) / len(validations))
    passed: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    for item in validations:
        passed.extend(item.get("passed_checks", []))
        warnings.extend(item.get("warnings", []))
        blocking.extend(item.get("blocking_issues", []))
    if blocking:
        score = min(score, 68)
    return _result(score, list(dict.fromkeys(passed)), list(dict.fromkeys(warnings)), list(dict.fromkeys(blocking)))


def validate_pack_consistency(pack: dict) -> dict:
    passed: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    penalty = 0
    route_spec = pack.get("route_spec") or {}
    lyrics_prompt = pack.get("lyrics_prompt") or ""
    route = route_spec.get("route")
    penalty += _add_check(bool(route and route_spec.get("section_map")), "route and section_map present", passed, warnings, blocking, True)
    if route_spec.get("section_map"):
        labels = [item.get("label") for item in route_spec["section_map"] if item.get("label")]
        penalty += _add_check(any(label in lyrics_prompt for label in labels), "lyrics prompt follows route section_map", passed, warnings, blocking, False)
    penalty += _add_check(pack.get("variant_role") in {"safe", "bold", "minimal", "exploratory"}, "variant_role explicit", passed, warnings, blocking, True)
    feedback_used = pack.get("source_trace", {}).get("feedback_used", [])
    if pack.get("feedback_summary", {}).get("review_count", 0):
        penalty += _add_check(bool(feedback_used), "feedback_used recorded", passed, warnings, blocking, False)
    validation_score = (pack.get("validation") or {}).get("score", 0)
    if pack.get("recommended"):
        penalty += _add_check(validation_score >= 70, "recommended pack has acceptable validation score", passed, warnings, blocking, True)
    return _result(100 - penalty, passed, warnings, blocking)
