from app.models import Song


FORBIDDEN_STYLE_TERMS = ["Mandarin", "Chinese", "普通话", "中文", "language-focused", "literary synopsis"]


def _genre_parts(song: Song) -> tuple[str, str]:
    direction = song.genre_direction or "minimal alternative pop / electronic ballad"
    parts = [part.strip() for part in direction.replace(",", "/").split("/") if part.strip()]
    primary = parts[0] if parts else "minimal alternative pop"
    secondary = parts[1] if len(parts) > 1 else "electronic ballad"
    return primary, secondary


def _base_hook(song: Song) -> str:
    if song.locked_hook:
        return song.locked_hook
    if "访问失败" in song.title:
        return "access denied"
    title = (song.title or "").strip()
    if title:
        return title if len(title) <= 12 else title[:12]
    return "别停下"


def _compact(value: str | None, fallback: str, limit: int = 120) -> str:
    text = " ".join((value or "").split())
    if not text:
        return fallback
    return text[:limit]


def _sonic_identity(song: Song, variant: str) -> str:
    concept = _compact(song.concept, song.title or "unfinished memory")
    function = _compact(song.function_in_ep, "a transitional EP track")
    emotion = _compact(song.emotional_goal, "restrained, unresolved, intimate")
    if variant == "experimental":
        return (
            f"sonic identity: translate `{concept}` into a colder repeated motif; EP function: {function}; "
            f"emotional target: {emotion}; use small system-like details as rhythm, not as spoken exposition"
        )
    if variant == "alternate":
        return (
            f"sonic identity: keep `{concept}` personal and close, but make the hook easier to remember; "
            f"EP function: {function}; emotional target: {emotion}; avoid decorative drama"
        )
    return (
        f"sonic identity: make `{concept}` feel like a usable song scene, not a summary; "
        f"EP function: {function}; emotional target: {emotion}; keep the production intimate and executable"
    )


def _arrangement_motion(route_label: str, variant: str) -> str:
    if route_label == "loop_mantra" or variant == "experimental":
        return "arrangement movement: loop-based intro, one motif mutates every 8 bars, no traditional big lift, final hook becomes thinner not bigger"
    if route_label == "classic_pop":
        return "arrangement movement: verse stays narrow, pre-chorus removes low end, chorus adds one doubled vocal and one higher pad, bridge strips drums"
    if route_label == "contrast_turn":
        return "arrangement movement: cold open exposes the hook, verse drops density, chorus pivots into a tighter pulse, bridge changes texture only once"
    return "arrangement movement: start with a small denial motif, verse adds room tone, pre-chorus tightens pulse, chorus repeats hook without a stadium lift"


def _style_specificity_score(style_prompt: str, song: Song) -> int:
    score = 40
    required_terms = ["sonic identity", "arrangement movement", "groove/drums", "bass", "vocal direction", "mix/space", "forbidden terms"]
    score += sum(7 for term in required_terms if term in style_prompt)
    if song.title and song.title in style_prompt:
        score += 6
    if song.concept and _compact(song.concept, "", 24)[:4] in style_prompt:
        score += 8
    if song.function_in_ep and _compact(song.function_in_ep, "", 24)[:4] in style_prompt:
        score += 5
    return max(0, min(100, score))


def _quality_checks(style_prompt: str, lyrics_prompt: str, hook: str) -> list[dict]:
    checks = [
        ("Style Prompt 不含语言标签", not any(term in style_prompt for term in FORBIDDEN_STYLE_TERMS)),
        ("包含 BPM", "BPM" in style_prompt),
        ("包含 groove/drums", "groove" in style_prompt and "drums" in style_prompt),
        ("包含 bass", "bass" in style_prompt),
        ("包含 vocal direction", "vocal direction" in style_prompt),
        ("包含 sonic identity", "sonic identity" in style_prompt),
        ("包含 arrangement movement", "arrangement movement" in style_prompt),
        ("包含 mix/space", "mix/space" in style_prompt),
        ("Lyrics Prompt 包含 Hook", hook in lyrics_prompt),
        ("包含 negative terms", "negative" in style_prompt.lower() or "forbidden" in style_prompt.lower()),
        ("包含修正策略", "Revision target" in lyrics_prompt),
    ]
    return [{"label": label, "passed": passed} for label, passed in checks]


def _pack(song: Song, variant: str, recommended: bool, route: str, mood_shift: str) -> dict:
    primary, secondary = _genre_parts(song)
    bpm = song.bpm or 88
    hook = _base_hook(song)
    route_label = route or song.current_structure_route or "error_system"
    style_prompt = (
        f"Track title: {song.title or 'untitled'}; primary genre: {primary}; secondary genre: {secondary}; BPM: {bpm}; "
        f"{_sonic_identity(song, variant)}; "
        "groove/drums: restrained mid-tempo pulse, dry kick, soft snare, sparse glitch ticks, no big drop; "
        "bass: warm sub bass with a simple pressure pattern that answers the hook, not a busy riff; "
        "harmony/instrument palette: muted electric piano, narrow synth pad, low system hum, one small motif tied to the song scene; "
        "vocal direction: close intimate lead, controlled breath, slightly tired consonants, doubled hook only on the second repeat; "
        f"{_arrangement_motion(route_label, variant)}; "
        f"mood: {song.emotional_goal or 'cold, stuck, intimate, unresolved'} {mood_shift}; "
        "mix/space: dry lead vocal, small room, low-volume background artifacts, leave silence before the first hook repeat; "
        "production constraints: sections must stay readable, chorus must not turn into a spoken essay; "
        "forbidden terms: no language labels, no cinematic trailer, no EDM drop, no rock anthem, no motivational anthem."
    )

    if route_label == "error_system":
        section_map = [
            ("[System Intro]", "2-4 bars, machine hum and a small denial motif."),
            ("[Verse - Cache]", "Concrete old chat / old room images, half-sung with short rests."),
            ("[Pre-Chorus - Retry]", "Shorter lines, rising tension, one repeated command-like phrase."),
            ("[Chorus - Access Failure]", f"Use the hook: {hook}. Repeat it, then answer with 可我停在你之外."),
            ("[Bridge - Old Version]", "Spoken or half-sung reflection; do not explain every metaphor."),
            ("[Final Chorus]", f"Return to {hook}, add a second voice with never try again."),
            ("[Outro]", "Fade on a failed-login phrase and room tone."),
        ]
    else:
        section_map = [
            ("[Intro]", "2-4 bars, establish pulse and motif."),
            ("[Verse]", "Concrete image, low vocal, leave rests."),
            ("[Chorus]", f"Short hook: {hook}. Repeat with one variation."),
            ("[Bridge]", "Half-sung reflection, minimal arrangement."),
            ("[Final Chorus]", "Return to hook with restrained doubles."),
            ("[Outro]", "Unresolved final fragment."),
        ]

    if song.lyrics.strip():
        lyrics_prompt = "\n".join(
            [
                "[Use these lyrics as the primary lyric source]",
                song.lyrics.strip(),
                "",
                "[Global vocal direction]",
                "Close, restrained, intimate. Keep the hook short and repeatable. Preserve the written lyric meaning; do not replace it with generic filler.",
                "",
                "[Section delivery notes]",
            ]
            + [f"{label}\n{body}" for label, body in section_map]
            + [
                "[Revision target]",
                "If the hook is not clear, simplify the chorus first. If the style drifts, adjust groove and instrument palette before changing lyrics.",
            ]
        )
    else:
        lyrics_prompt = "\n".join(
            [
                "[Lyric drafting mode]",
                "No accepted full lyric draft is available yet. Use the section notes below as a temporary writing scaffold, not as final lyrics.",
                "[Global vocal direction]\nClose, restrained, intimate. Keep the hook short and repeatable.",
            ]
            + [f"{label}\n{body}" for label, body in section_map]
            + [
                "[Revision target]\nIf the hook is not clear, simplify the chorus first. If the style drifts, adjust groove and instrument palette before changing lyrics."
            ]
        )

    return {
        "variant": variant,
        "recommended": recommended,
        "recommendation_reason": "主线版本最稳，Hook 位置清楚，结构能让 Suno 读懂错误系统的叙事。" if recommended else "作为对照版本，用来测试风格或结构边界。",
        "style_prompt": style_prompt,
        "lyrics_prompt": lyrics_prompt,
        "lyrics_source": "accepted_song_lyrics" if song.lyrics.strip() else "temporary_structure_scaffold",
        "negative_terms": FORBIDDEN_STYLE_TERMS,
        "hook_delivery_notes": f"Hook `{hook}` 必须短句重复，第一次冷，第二次加轻微叠唱。",
        "section_control_notes": f"结构路线：{route_label}。段落标签服务生成稳定性，不等于固定模板。",
        "revision_strategy": "Hook 不清楚就改 Lyrics Prompt；风格偏离就改 Style Prompt；段落混乱就减少标签和缩短副歌。",
        "suno_risks": ["副歌句子过长会变成朗读", "Style Prompt 写语言标签会污染风格", "抽象概念堆叠会削弱可唱性"],
        "quality_checks": _quality_checks(style_prompt, lyrics_prompt, hook),
        "style_specificity_score": _style_specificity_score(style_prompt, song),
    }


def build_suno_prompt_packs(song: Song) -> dict:
    packs = [
        _pack(song, "primary", True, song.current_structure_route or "error_system", "with a clean executable alt-pop shape"),
        _pack(song, "alternate", False, "classic_pop", "slightly warmer and more hook-focused"),
        _pack(song, "experimental", False, "loop_mantra", "colder, more repetitive, more system-like"),
    ]
    return {"packs": packs, "recommended_variant": "primary", "recommended_pack": packs[0]}


def legacy_suno_response(song: Song):
    from app.schemas import SunoResponse

    pack_data = build_suno_prompt_packs(song)
    pack = pack_data["recommended_pack"]
    return SunoResponse(
        title=song.title,
        style_prompt=pack["style_prompt"],
        lyrics_prompt=pack["lyrics_prompt"],
        negative_style_terms=pack["negative_terms"],
        bpm=song.bpm or 92,
        generation_notes=pack["revision_strategy"],
    )
