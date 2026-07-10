from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreativeArtifact, Song
from app.services.suno_feedback import summarize_generation_reviews
from app.services.suno_routes import get_route_spec
from app.services.suno_spec import LANGUAGE_LABELS, normalize_song_to_music_spec
from app.services.suno_validation import (
    merge_validations,
    validate_exclude_prompt,
    validate_lyrics_prompt,
    validate_pack_consistency,
    validate_style_prompt,
)


FORBIDDEN_STYLE_TERMS = LANGUAGE_LABELS


VARIANTS = [
    {
        "variant": "primary",
        "variant_role": "safe",
        "settings": {"weirdness": 30, "style_influence": 78, "audio_influence": None},
        "style_shift": "keep the most stable brief-faithful palette",
        "groove_shift": "steady dry kick and soft snare pocket",
        "instrument_shift": "muted electric piano leads the harmony",
        "lyric_shift": "clarity first, chorus hook repeated plainly",
    },
    {
        "variant": "alternate",
        "variant_role": "bold",
        "settings": {"weirdness": 46, "style_influence": 70, "audio_influence": None},
        "style_shift": "change one or two variables: add sharper syncopation and a more tactile motif",
        "groove_shift": "sharper syncopated hats, lighter kick, tactile percussion clicks",
        "instrument_shift": "replace some keys with plucked synth and a small glassy motif",
        "lyric_shift": "slightly stronger pre-chorus lift and more memorable hook entrance",
    },
    {
        "variant": "experimental",
        "variant_role": "minimal",
        "settings": {"weirdness": 24, "style_influence": 64, "audio_influence": None},
        "style_shift": "shorter, drier, fewer layers, faster to test",
        "groove_shift": "minimal pulse, fewer drum events, more silence before hook returns",
        "instrument_shift": "remove pad density and leave bass, dry vocal, and one echo motif",
        "lyric_shift": "minimal labels, shorter lines, one clean echo",
    },
]


def _compact(value: str | None, fallback: str, limit: int = 180) -> str:
    text = " ".join((value or "").split())
    return (text or fallback)[:limit]


def _accepted_artifacts(db: Session | None, song: Song) -> list[CreativeArtifact]:
    if db is None:
        return []
    return list(
        db.scalars(
            select(CreativeArtifact)
            .where(CreativeArtifact.song_id == song.id)
            .where(CreativeArtifact.status == "accepted")
            .order_by(CreativeArtifact.updated_at.desc())
        ).all()
    )


def _hook(song: Song, music_spec: dict) -> str:
    if music_spec.get("accepted_hook"):
        return str(music_spec["accepted_hook"])
    title = (song.title or "").strip()
    return title[:18] if title else "stay with me"


def _route(song: Song, variant: str) -> dict:
    route = song.current_structure_route or "classic_pop"
    if variant == "experimental" and route == "classic_pop":
        route = "through_composed"
    return get_route_spec(route)


def _feedback_clause(feedback_summary: dict) -> str:
    if not feedback_summary.get("review_count"):
        return "feedback loop: prior generation review unavailable."
    return f"feedback loop: {feedback_summary.get('next_revision_bias') or 'use recent review notes to keep the next test focused'}."


def _style_prompt(song: Song, music_spec: dict, route_spec: dict, variant_config: dict, feedback_summary: dict) -> str:
    instrumentation = ", ".join(music_spec["instrumentation"])
    textures = ", ".join(music_spec["production_texture"])
    harmony = ", ".join(music_spec["harmony_palette"])
    return (
        f"Track title: {song.title or 'untitled'}; "
        f"primary genre: {music_spec['primary_genre']}; secondary genre: {music_spec['secondary_genre']}; "
        f"BPM: {music_spec['bpm']}; tempo feel: {music_spec['tempo_feel']}; "
        f"use case: {_compact(song.function_in_ep, 'EP production track')}; "
        f"mood: {music_spec['mood']}; "
        f"vocal direction: {music_spec['vocal_type']}, {music_spec['vocal_delivery']}; "
        f"instrumentation: {instrumentation}; "
        f"groove/drums: {music_spec['rhythm_groove']}; "
        f"bass/low-end: {music_spec['bass_behavior']}; "
        f"harmony/instrument palette: {harmony}; "
        f"production texture: {textures}; "
        f"arrangement movement: {route_spec['arrangement_motion']}; "
        f"variant behavior: {variant_config['style_shift']}; "
        f"variant groove: {variant_config['groove_shift']}; "
        f"variant instrumentation: {variant_config['instrument_shift']}; "
        f"mix/space: {music_spec['mix_space']}; energy curve: {music_spec['energy_curve']}; "
        f"{_feedback_clause(feedback_summary)} "
        "production constraints: readable section changes, singable chorus, original-reference-safe palette."
    )


def _section_delivery_notes(route_spec: dict, feedback_summary: dict) -> list[str]:
    lines = []
    hook_problem = "hook_clarity" in (feedback_summary.get("recurring_problems") or [])
    for section in route_spec["section_map"]:
        instruction = section["hook_instruction"]
        if hook_problem and "hook" in instruction.lower():
            instruction += "; strengthen hook repetition and chorus clarity"
        lines.append(f"{section['label']}: {section['purpose']}; {section['delivery']}; {instruction}")
    return lines


def _lyrics_prompt(song: Song, music_spec: dict, route_spec: dict, variant_config: dict, feedback_summary: dict, hook: str) -> str:
    hook_repeats = 3 if "hook_clarity" in (feedback_summary.get("recurring_problems") or []) else 2
    if song.lyrics.strip():
        lyrics = song.lyrics.strip()
        if hook and lyrics.count(hook) < hook_repeats:
            lyrics = f"{lyrics}\n\n[Chorus]\n" + "\n".join([hook] * hook_repeats)
        return lyrics

    verse_seed = _compact(song.concept or song.function_in_ep, "late light in a small room", 80)
    chorus_lines = "\n".join([hook] * hook_repeats)
    if variant_config["variant_role"] == "minimal":
        return f"""[Verse]
{verse_seed}
I leave the loud part out

[Chorus]
{chorus_lines}

[Echo]
{hook}"""
    if route_spec["route"] == "through_composed":
        return f"""[Opening]
{verse_seed}

[Development]
I move the line before it settles

[Echo Phrase]
{hook}

[Final Echo]
{hook}"""
    return "\n".join(
        [
            "[Verse]",
            verse_seed,
            "",
            "[Pre-Chorus]",
            "I keep the sentence small",
            "I let the silence answer",
            "",
            "[Chorus]",
            chorus_lines,
            "",
            "[Bridge]",
            "one old image changes shape",
            "",
            "[Final Chorus]",
            chorus_lines,
        ]
    )


def _exclude_prompt(feedback_summary: dict, variant_role: str) -> str:
    terms = [
        "no artist imitation",
        "no spoken essay verses",
        "no arena rock chorus",
        "no EDM drop",
        "no muddy low-end",
        "no excessive reverb on lead vocal",
    ]
    recurring = feedback_summary.get("recurring_problems") or []
    if "heavy_drums" in recurring:
        terms.append("avoid heavy drums, soften percussion density")
    if "over_sweet_vocal" in recurring:
        terms.append("avoid overly sweet vocal tone, keep vocal restrained")
    if "unclear_verse_diction" in recurring:
        terms.append("avoid long unclear verse lines")
    if variant_role == "minimal":
        terms.append("avoid extra percussion fills and decorative countermelodies")
    return "; ".join(terms) + "."


def _style_specificity_score(style_prompt: str, validation: dict) -> int:
    anchor_terms = ["primary genre", "secondary genre", "BPM", "vocal direction", "instrumentation", "groove/drums", "bass/low-end", "mix/space", "arrangement movement"]
    score = 35 + sum(6 for term in anchor_terms if term in style_prompt)
    score += max(0, validation.get("score", 0) - 70) // 2
    return max(0, min(100, int(score)))


def _quality_checks(validation: dict) -> list[dict]:
    checks = [{"label": item, "passed": True} for item in validation.get("passed_checks", [])]
    checks.extend({"label": item, "passed": False} for item in validation.get("warnings", []))
    checks.extend({"label": item, "passed": False} for item in validation.get("blocking_issues", []))
    return checks


def _pack(song: Song, music_spec: dict, route_spec: dict, variant_config: dict, feedback_summary: dict) -> dict:
    hook = _hook(song, music_spec)
    style = _style_prompt(song, music_spec, route_spec, variant_config, feedback_summary)
    lyrics = _lyrics_prompt(song, music_spec, route_spec, variant_config, feedback_summary, hook)
    exclude = _exclude_prompt(feedback_summary, variant_config["variant_role"])
    style_validation = validate_style_prompt(style, music_spec)
    lyrics_validation = validate_lyrics_prompt(lyrics, hook, route_spec)
    exclude_validation = validate_exclude_prompt(exclude, style)
    validation = merge_validations(style_validation, lyrics_validation, exclude_validation)
    source_trace = {
        "harness_stages": ["Brief", "Normalize", "Compose", "Validate", "Variant", "Package", "Learn", "Iterate"],
        "hook": hook,
        "structure_route": route_spec["route"],
        "lyrics_source": "accepted_song_lyrics" if song.lyrics.strip() else "temporary_structure_scaffold",
        "feedback_used": feedback_summary.get("feedback_used", []),
        "source_review_ids": [item.get("artifact_id") for item in feedback_summary.get("feedback_used", []) if item.get("artifact_id")],
    }
    pack = {
        "variant": variant_config["variant"],
        "variant_role": variant_config["variant_role"],
        "recommended": False,
        "recommendation_reason": "",
        "music_spec": music_spec,
        "route_spec": route_spec,
        "style_prompt": style,
        "lyrics_prompt": lyrics,
        "exclude_prompt": exclude,
        "advanced_settings": variant_config["settings"],
        "validation": validation,
        "negative_terms": FORBIDDEN_STYLE_TERMS,
        "hook_delivery_notes": f"Hook `{hook}` should be short, repeated, and placed where the route says it will be heard.",
        "section_control_notes": f"Route `{route_spec['route']}`: {route_spec['stability_notes']}",
        "revision_strategy": feedback_summary.get("next_revision_bias") or "If hook clarity fails, simplify the chorus first; if style drifts, adjust groove and instrument palette before rewriting lyrics.",
        "suno_risks": route_spec.get("suno_risks", []),
        "source_trace": source_trace,
        "style_specificity_score": 0,
        "quality_checks": [],
        "lyrics_source": source_trace["lyrics_source"],
        "feedback_summary": feedback_summary,
        "lyrics_control_notes": _section_delivery_notes(route_spec, feedback_summary),
    }
    consistency = validate_pack_consistency(pack)
    pack["validation"] = merge_validations(validation, consistency)
    pack["style_specificity_score"] = _style_specificity_score(style, pack["validation"])
    pack["quality_checks"] = _quality_checks(pack["validation"])
    return pack


def _recommend(packs: list[dict], feedback_summary: dict) -> dict:
    scored = []
    problems = set(feedback_summary.get("recurring_problems") or [])
    for pack in packs:
        validation_score = pack["validation"]["score"]
        route_score = int(pack["route_spec"].get("stability_score", 5)) * 2
        role_bonus = {"safe": 4, "bold": 2, "minimal": 1, "exploratory": 0}.get(pack["variant_role"], 0)
        feedback_bonus = 0
        if feedback_summary.get("review_count") and pack["source_trace"]["feedback_used"]:
            if "heavy_drums" in problems or "production_unusable" in problems:
                feedback_bonus += 5 if pack["variant_role"] == "minimal" else 1
            if "style_drift" in problems:
                feedback_bonus += 4 if pack["variant_role"] == "safe" else 2
            if "hook_clarity" in problems:
                feedback_bonus += int(pack["route_spec"].get("stability_score", 5))
        blocking_penalty = 1000 if pack["validation"].get("blocking_issues") and any(
            not candidate["validation"].get("blocking_issues") for candidate in packs
        ) else 30 if pack["validation"].get("blocking_issues") else 0
        scored.append((validation_score + route_score + role_bonus + feedback_bonus - blocking_penalty, pack))
    scored.sort(key=lambda item: (item[0], item[1]["validation"]["score"]), reverse=True)
    recommended = scored[0][1]
    for _, pack in scored:
        pack["recommended"] = pack is recommended
        pack["recommendation_reason"] = (
            f"Selected by validation score {pack['validation']['score']}, route stability {pack['route_spec'].get('stability_score', 0)}, "
            f"role `{pack['variant_role']}`, and feedback fit."
            if pack is recommended
            else f"Kept as a comparison variant: {pack['variant_role']} changes a different musical variable."
        )
    return recommended


def _refresh_post_recommend_validation(packs: list[dict]) -> None:
    for pack in packs:
        consistency = validate_pack_consistency(pack)
        pack["validation"] = merge_validations(pack["validation"], consistency)
        pack["style_specificity_score"] = _style_specificity_score(pack["style_prompt"], pack["validation"])
        pack["quality_checks"] = _quality_checks(pack["validation"])


def build_suno_prompt_packs(song: Song, db: Session | None = None) -> dict:
    accepted = _accepted_artifacts(db, song)
    feedback_summary = summarize_generation_reviews(db, song) if db is not None else {
        "review_count": 0,
        "winning_terms": [],
        "blocked_terms": [],
        "recurring_problems": [],
        "next_revision_bias": "",
        "feedback_used": [],
    }
    music_spec = normalize_song_to_music_spec(song, accepted, feedback_summary)
    packs = []
    for config in VARIANTS:
        packs.append(_pack(song, music_spec, _route(song, config["variant"]), config, feedback_summary))
    recommended = _recommend(packs, feedback_summary)
    _refresh_post_recommend_validation(packs)
    return {
        "packs": packs[:3],
        "recommended_variant": recommended["variant"],
        "recommended_pack": recommended,
        "feedback_summary": feedback_summary,
    }


def legacy_suno_response(song: Song, db: Session | None = None):
    from app.schemas import SunoResponse

    pack_data = build_suno_prompt_packs(song, db=db)
    pack = pack_data["recommended_pack"]
    return SunoResponse(
        title=song.title,
        style_prompt=pack["style_prompt"],
        lyrics_prompt=pack["lyrics_prompt"],
        negative_style_terms=pack["negative_terms"],
        bpm=song.bpm or 92,
        generation_notes=pack["revision_strategy"],
    )
