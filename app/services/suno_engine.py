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


def _quality_checks(style_prompt: str, lyrics_prompt: str, hook: str) -> list[dict]:
    checks = [
        ("Style Prompt 不含语言标签", not any(term in style_prompt for term in FORBIDDEN_STYLE_TERMS)),
        ("包含 BPM", "BPM" in style_prompt),
        ("包含 groove/drums", "groove" in style_prompt and "drums" in style_prompt),
        ("包含 bass", "bass" in style_prompt),
        ("包含 vocal direction", "vocal direction" in style_prompt),
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
        f"Primary genre: {primary}; secondary genre: {secondary}; BPM: {bpm}; "
        "groove/drums: restrained mid-tempo pulse, dry kick, soft snare, sparse glitch ticks, no big drop; "
        "bass: warm sub bass repeating a simple two-note pressure pattern; "
        "harmony/instrument palette: muted electric piano, narrow synth pad, low system hum, small alert-like motifs; "
        "vocal direction: close intimate lead, controlled breath, doubled hook only on the second repeat; "
        f"mood: {song.emotional_goal or 'cold, stuck, intimate, unresolved'} {mood_shift}; "
        "production constraints: leave negative space around the hook, keep sections readable; "
        "forbidden terms: no language labels, no cinematic trailer, no EDM drop, no rock anthem, no spoken essay."
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

    lyrics_prompt = "\n".join(
        ["[Global vocal direction]\nClose, restrained, intimate. Keep the hook short and repeatable."]
        + [f"{label}\n{body}" for label, body in section_map]
        + ["[Revision target]\nIf the hook is not clear, simplify the chorus first. If the style drifts, adjust groove and instrument palette before changing lyrics."]
    )

    return {
        "variant": variant,
        "recommended": recommended,
        "recommendation_reason": "主线版本最稳，Hook 位置清楚，结构能让 Suno 读懂错误系统的叙事。" if recommended else "作为对照版本，用来测试风格或结构边界。",
        "style_prompt": style_prompt,
        "lyrics_prompt": lyrics_prompt,
        "negative_terms": FORBIDDEN_STYLE_TERMS,
        "hook_delivery_notes": f"Hook `{hook}` 必须短句重复，第一次冷，第二次加轻微叠唱。",
        "section_control_notes": f"结构路线：{route_label}。段落标签服务生成稳定性，不等于固定模板。",
        "revision_strategy": "Hook 不清楚就改 Lyrics Prompt；风格偏离就改 Style Prompt；段落混乱就减少标签和缩短副歌。",
        "suno_risks": ["副歌句子过长会变成朗读", "Style Prompt 写语言标签会污染风格", "抽象概念堆叠会削弱可唱性"],
        "quality_checks": _quality_checks(style_prompt, lyrics_prompt, hook),
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
