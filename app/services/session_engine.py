import json
import re

from sqlalchemy.orm import Session

from app.llm.deepseek_client import DeepSeekClient
from app.models import CreativeArtifact, CreativeSession, EPState, Song
from app.prompts.producer_system_prompt import PRODUCER_SYSTEM_PROMPT
from app.services.hooks import generate_hooks
from app.services.stages import next_stage
from app.services.suno_engine import build_suno_prompt_packs


def _is_access_failure_song(song: Song) -> bool:
    haystack = " ".join([song.title or "", song.concept or "", song.function_in_ep or "", song.notes or ""]).lower()
    return "访问失败" in haystack or "access denied" in haystack


def _core_material(song: Song) -> str:
    return song.concept or song.function_in_ep or song.emotional_goal or song.title


def _short_hook_seed(song: Song) -> str:
    if song.locked_hook:
        return song.locked_hook
    if _is_access_failure_song(song):
        return "access denied"
    title = (song.title or "别停下").strip()
    return title if len(title) <= 12 else title[:12]


def _as_list(value, fallback: list | None = None) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return fallback or []
    return [value]


def _json_from_model_text(text: str) -> dict | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    raw = fenced.group(1) if fenced else text
    if "{" in raw and "}" in raw:
        raw = raw[raw.find("{") : raw.rfind("}") + 1]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


GENERIC_LYRIC_PHRASES = [
    "世界太吵",
    "落在心上",
    "星辰大海",
    "眼泪的重量",
    "黑夜尽头",
    "拥抱孤单",
    "时间会回答",
    "人海",
    "命运",
    "永远",
]


def _meaningful_fragments(*values: str | None) -> list[str]:
    fragments: list[str] = []
    for value in values:
        if not value:
            continue
        cleaned = re.sub(r"[\s,，。.!！?？、/\\|:：;；()\[\]{}<>《》\"'“”‘’]+", " ", value)
        for part in cleaned.split():
            part = part.strip()
            if len(part) >= 2 and part not in fragments:
                fragments.append(part)
    return fragments[:12]


def _score_lyrics_quality(song: Song, lyrics: str, model_data: dict | None = None) -> dict:
    score = 100
    issues: list[str] = []
    strengths: list[str] = []
    section_count = len(re.findall(r"^\[[^\]]+\]", lyrics, flags=re.MULTILINE))

    if len(lyrics.strip()) < 180:
        score -= 22
        issues.append("歌词长度偏短，还不像一版完整可测试的歌。")
    if section_count < 4:
        score -= 15
        issues.append("段落标签不足，Suno 很可能读不清主歌/副歌/桥段。")
    else:
        strengths.append("段落结构可被 Suno 识别。")

    hook = (song.locked_hook or str((model_data or {}).get("hook") or "")).strip()
    if hook:
        hook_count = lyrics.count(hook)
        if hook_count == 0:
            score -= 30
            issues.append("没有原样保留已锁定 Hook。")
        elif hook_count == 1:
            score -= 8
            issues.append("Hook 只出现一次，记忆点可能不够。")
        else:
            strengths.append("Hook 有重复，适合作为副歌锚点。")

    generic_hits = [phrase for phrase in GENERIC_LYRIC_PHRASES if phrase in lyrics]
    if generic_hits:
        score -= min(20, len(generic_hits) * 5)
        issues.append(f"出现泛化套话：{'、'.join(generic_hits[:4])}。")

    fragments = _meaningful_fragments(song.title, song.concept, song.function_in_ep, song.emotional_goal)
    matched = [fragment for fragment in fragments if fragment in lyrics]
    if fragments and not matched:
        score -= 18
        issues.append("没有把歌名/概念/EP 功能里的具体材料写进歌词。")
    elif matched:
        strengths.append(f"已吸收核心材料：{'、'.join(matched[:3])}。")

    chorus_blocks = re.findall(r"\[Chorus[^\]]*\](.*?)(?=\n\[[^\]]+\]|\Z)", lyrics, flags=re.DOTALL | re.IGNORECASE)
    if chorus_blocks:
        longest_chorus = max(len(block.strip()) for block in chorus_blocks)
        if longest_chorus > 220:
            score -= 10
            issues.append("副歌段落偏长，可能被唱成说明文字。")
    else:
        score -= 12
        issues.append("没有明确 Chorus，Hook 落点不够清楚。")

    if re.search(r"Lyrics Prompt|Style Prompt|写作说明|创作策略", lyrics, flags=re.IGNORECASE):
        score -= 25
        issues.append("歌词里混入了 Prompt 或说明文字。")

    model_score = (model_data or {}).get("quality_score")
    if isinstance(model_score, int | float):
        score = round((score * 0.75) + (max(0, min(100, int(model_score))) * 0.25))

    score = max(0, min(100, int(score)))
    if score >= 76:
        band = "pass"
    elif score >= 62:
        band = "needs_review"
    else:
        band = "retry_or_rewrite"
    return {
        "quality_score": score,
        "quality_band": band,
        "quality_passed": score >= 70,
        "quality_issues": issues,
        "quality_strengths": strengths,
    }


def _lyrics_retry_prompt(context: dict, lyrics: str, quality: dict) -> str:
    return (
        f"{_stage_prompt('lyrics_draft', context)}\n\n"
        "上一版歌词没有达到 V1 可测试标准，请只返回同一 JSON contract 的重写结果。\n"
        f"上一版质量评分：{quality['quality_score']}/100\n"
        f"必须修复的问题：{json.dumps(quality['quality_issues'], ensure_ascii=False)}\n"
        "重写要求：保留 locked_hook 原文；减少套话；增加具体画面；副歌短且可重复；不要输出说明文字。\n\n"
        f"上一版歌词：\n{lyrics}"
    )


def _context_payload(song: Song, ep: EPState, stage: str, user_goal: str, user_message: str) -> dict:
    return {
        "stage": stage,
        "user_goal": user_goal,
        "user_message": user_message,
        "ep": {
            "title": ep.title,
            "one_liner": ep.one_liner,
            "core_theme": ep.core_theme,
            "world_view": ep.world_view,
            "emotional_keywords": ep.emotional_keywords,
            "aesthetic_keywords": ep.aesthetic_keywords,
            "sonic_layers": ep.sonic_layers,
            "narrative_arc": ep.narrative_arc,
        },
        "song": {
            "title": song.title,
            "function_in_ep": song.function_in_ep,
            "concept": song.concept,
            "emotional_goal": song.emotional_goal,
            "bpm": song.bpm,
            "genre_direction": song.genre_direction,
            "language_plan": song.language_plan,
            "lyrics": song.lyrics,
            "locked_hook": song.locked_hook,
            "current_structure_route": song.current_structure_route,
            "notes": song.notes,
        },
    }


def _stage_prompt(stage: str, context: dict) -> str:
    contracts = {
        "diagnosis": {
            "artifact_type": "diagnosis",
            "required_json": {
                "assistant_message": "中文，像制作人一样指出这首歌现在最该解决什么",
                "ep_function": "这首歌在 EP 里的功能",
                "biggest_problem": "当前最大创作问题",
                "strongest_material": ["最有用的歌名/画面/短句/声音线索"],
                "recommended_next_stage": "hook_lab",
                "risks": ["至少 3 条风险"],
                "next_actions": ["2-4 个下一步动作"],
            },
        },
        "hook_lab": {
            "artifact_type": "hook_set",
            "required_json": {
                "assistant_message": "中文，说明推荐哪个 Hook 和为什么",
                "recommended_hook": "最推荐的一句 Hook",
                "hooks": [
                    {
                        "hook_text": "短、可重复、可唱",
                        "why_it_works": "为什么成立",
                        "rhythm_notes": "节奏/落拍/重复方式",
                        "suno_risk": "给 Suno 的风险",
                        "score": 1,
                    }
                ],
                "next_actions": ["2-4 个下一步动作"],
            },
        },
        "structure_lab": {
            "artifact_type": "structure_route",
            "required_json": {
                "assistant_message": "中文，推荐稳定路线，也保留创新选择",
                "recommended_route": "classic_pop 或自定义 snake_case",
                "routes": [
                    {
                        "route": "snake_case",
                        "label": "中文路线名",
                        "why": "为什么适合这首歌",
                        "section_map": [{"section": "段落名", "function": "这一段承担什么"}],
                        "hook_placement": ["Hook 出现位置"],
                        "stability": 1,
                        "innovation": 1,
                        "suno_risks": ["风险"],
                        "how_to_feed_suno": "如何写进 Suno Lyrics Prompt",
                    }
                ],
                "next_actions": ["2-4 个下一步动作"],
            },
        },
        "lyrics_draft": {
            "artifact_type": "lyrics_draft",
            "required_json": {
                "assistant_message": "中文，说明歌词草稿策略",
                "hook": "使用的 Hook",
                "lyrics": "完整歌词草稿。必须是真歌词，不是写给 Suno 的说明。保留段落标签。",
                "section_notes": [{"section": "段落名", "purpose": "功能"}],
                "singability_risks": ["可唱性风险"],
                "revision_targets": ["下一轮最该改哪里"],
                "next_actions": ["2-4 个下一步动作"],
            },
        },
        "generation_review": {
            "artifact_type": "generation_review",
            "required_json": {
                "assistant_message": "中文，根据用户反馈判断下一轮优先改哪里",
                "next_revision_target": "hook/style/lyrics/structure/production 之一",
                "next_revision_advice": "具体修改建议",
                "keep": ["应该保留什么"],
                "change": ["应该修改什么"],
                "next_actions": ["2-4 个下一步动作"],
            },
        },
    }
    contract = contracts[stage]
    lyrics_quality_rules = ""
    if stage == "lyrics_draft":
        lyrics_quality_rules = (
            "\n歌词草稿质量标准：\n"
            "- 先像词作者一样写完整可唱歌词，不要写 Lyrics Prompt、创作说明或散文大纲。\n"
            "- 必须吸收 song.title、song.concept、song.function_in_ep、song.emotional_goal 里的具体材料；不要只写通用情绪。\n"
            "- 副歌优先短句、重复、可记忆；如果 song.locked_hook 非空，必须原样出现至少两次。\n"
            "- 主歌给具体画面和动作，桥段只给一个新角度，不要解释整首歌的设定。\n"
            "- 避免套话：世界太吵、落在心上、星辰大海、眼泪的重量、黑夜尽头、时间会回答、人海、命运、永远，除非用户材料本来就包含。\n"
            "- JSON 里必须给 quality_score(1-100)、quality_notes、revision_targets；低于 75 代表你自己也认为还不能直接测试。\n"
        )
    return (
        f"{PRODUCER_SYSTEM_PROMPT}\n\n"
        "你正在 EP Creative OS 的主流程中工作。请真正承担制作人/词作者/结构顾问职责，不要只给模板。\n"
        "只返回一个 JSON 对象，不要 Markdown，不要解释 JSON 以外的文字。\n"
        "所有用户可见内容用中文；后端枚举值可用英文 snake_case。\n"
        "歌词阶段必须输出完整歌词草稿，不要输出 Lyrics Prompt 或写作说明。\n"
        "如果 song.locked_hook 非空，歌词必须原样包含这个 locked_hook，优先放在 Chorus 开头并重复。\n"
        "Suno 风险可以提，但不要把 Style Prompt 的语言标签写成 Mandarin/Chinese/普通话/中文。\n"
        f"{lyrics_quality_rules}\n"
        f"当前阶段契约：{json.dumps(contract, ensure_ascii=False)}\n\n"
        f"项目上下文：{json.dumps(context, ensure_ascii=False)}"
    )


async def _try_ai_stage(
    song: Song,
    ep: EPState,
    stage: str,
    user_goal: str,
    user_message: str,
) -> tuple[str, list[dict], list[str]] | None:
    if stage not in {"diagnosis", "hook_lab", "structure_lab", "lyrics_draft", "generation_review"}:
        return None

    context = _context_payload(song, ep, stage, user_goal, user_message)
    client = DeepSeekClient()
    ok, text = await client.chat(
        [
            {"role": "system", "content": PRODUCER_SYSTEM_PROMPT},
            {"role": "user", "content": _stage_prompt(stage, context)},
        ],
        temperature=0.85 if stage in {"hook_lab", "lyrics_draft"} else 0.55,
        max_tokens=12000 if stage == "lyrics_draft" else 8000 if stage == "structure_lab" else 5000,
        json_mode=True,
    )
    if not ok:
        return None
    data = _json_from_model_text(text)
    if not data:
        return None

    source = {"source": "ai", "model": "deepseek", "fallback": False}
    assistant_message = data.get("assistant_message") or "AI 已生成本阶段创作建议。"
    next_actions = _as_list(data.get("next_actions"), ["保存本阶段产物", "进入下一阶段"])

    if stage == "diagnosis":
        content = {
            "ep_function": data.get("ep_function") or song.function_in_ep,
            "biggest_problem": data.get("biggest_problem") or "",
            "strongest_material": _as_list(data.get("strongest_material")),
            "recommended_next_stage": data.get("recommended_next_stage") or "hook_lab",
            "risks": _as_list(data.get("risks")),
            **source,
        }
        artifacts = [
            {
                "artifact_type": "diagnosis",
                "title": f"{song.title} / AI 歌曲诊断",
                "summary": content["biggest_problem"] or "AI 诊断当前创作方向。",
                "content": content,
                "is_recommended": True,
            }
        ]
        return assistant_message, artifacts, next_actions

    if stage == "hook_lab":
        hooks = _as_list(data.get("hooks"))
        normalized_hooks = []
        for index, hook in enumerate(hooks[:5]):
            if not isinstance(hook, dict):
                continue
            normalized_hooks.append(
                {
                    "hook_text": str(hook.get("hook_text") or "").strip(),
                    "why_it_works": hook.get("why_it_works") or "",
                    "rhythm_notes": hook.get("rhythm_notes") or "",
                    "suno_risk": hook.get("suno_risk") or "",
                    "score": int(hook.get("score") or max(60, 90 - index * 5)),
                }
            )
        recommended = data.get("recommended_hook") or (normalized_hooks[0]["hook_text"] if normalized_hooks else _short_hook_seed(song))
        content = {"hooks": normalized_hooks, "recommended_hook": recommended, **source}
        artifacts = [
            {
                "artifact_type": "hook_set",
                "title": f"{song.title} / AI Hook 候选组",
                "summary": f"AI 推荐 Hook：{recommended}",
                "content": content,
                "is_recommended": True,
            }
        ]
        return assistant_message, artifacts, next_actions

    if stage == "structure_lab":
        content = {
            "recommended_route": data.get("recommended_route") or "classic_pop",
            "routes": _as_list(data.get("routes")),
            **source,
        }
        artifacts = [
            {
                "artifact_type": "structure_route",
                "title": f"{song.title} / AI 结构路线",
                "summary": f"AI 推荐结构：{content['recommended_route']}",
                "content": content,
                "is_recommended": True,
            }
        ]
        return assistant_message, artifacts, next_actions

    if stage == "lyrics_draft":
        lyrics = str(data.get("lyrics") or "").strip()
        hook = song.locked_hook or data.get("hook") or _short_hook_seed(song)
        postprocess_notes = []
        if song.locked_hook and song.locked_hook not in lyrics:
            if "[Chorus]" in lyrics:
                lyrics = lyrics.replace("[Chorus]", f"[Chorus]\n{song.locked_hook}\n{song.locked_hook}", 1)
            else:
                lyrics = f"{lyrics}\n\n[Chorus]\n{song.locked_hook}\n{song.locked_hook}"
            postprocess_notes.append("AI 未原样保留锁定 Hook，系统已把锁定 Hook 插入副歌开头。")
        quality = _score_lyrics_quality(song, lyrics, data)
        retry_count = 0
        if not quality["quality_passed"]:
            retry_count = 1
            retry_ok, retry_text = await client.chat(
                [
                    {"role": "system", "content": PRODUCER_SYSTEM_PROMPT},
                    {"role": "user", "content": _lyrics_retry_prompt(context, lyrics, quality)},
                ],
                temperature=0.72,
                max_tokens=12000,
                json_mode=True,
            )
            retry_data = _json_from_model_text(retry_text) if retry_ok else None
            retry_lyrics = str((retry_data or {}).get("lyrics") or "").strip()
            if retry_data and len(retry_lyrics) >= 40:
                retry_notes = []
                if song.locked_hook and song.locked_hook not in retry_lyrics:
                    if "[Chorus]" in retry_lyrics:
                        retry_lyrics = retry_lyrics.replace("[Chorus]", f"[Chorus]\n{song.locked_hook}\n{song.locked_hook}", 1)
                    else:
                        retry_lyrics = f"{retry_lyrics}\n\n[Chorus]\n{song.locked_hook}\n{song.locked_hook}"
                    retry_notes.append("AI 返工稿仍未原样保留锁定 Hook，系统已把锁定 Hook 插入副歌开头。")
                retry_quality = _score_lyrics_quality(song, retry_lyrics, retry_data)
                if retry_quality["quality_score"] >= quality["quality_score"]:
                    data = retry_data
                    lyrics = retry_lyrics
                    hook = song.locked_hook or data.get("hook") or hook
                    postprocess_notes = retry_notes
                    quality = retry_quality
        if len(lyrics) < 40:
            return None
        content = {
            "lyrics": lyrics,
            "hook": hook,
            "section_notes": _as_list(data.get("section_notes")),
            "singability_risks": _as_list(data.get("singability_risks")),
            "revision_targets": _as_list(data.get("revision_targets")),
            "postprocess_notes": postprocess_notes,
            "quality_score": quality["quality_score"],
            "quality_band": quality["quality_band"],
            "quality_passed": quality["quality_passed"],
            "quality_issues": quality["quality_issues"],
            "quality_strengths": quality["quality_strengths"],
            "quality_notes": _as_list(data.get("quality_notes")),
            "ai_retry_count": retry_count,
            **source,
        }
        artifacts = [
            {
                "artifact_type": "lyrics_draft",
                "title": f"{song.title} / AI 歌词草稿",
                "summary": f"AI 基于 Hook「{hook}」生成完整歌词草稿。",
                "content": content,
                "is_recommended": True,
            }
        ]
        return assistant_message, artifacts, next_actions

    if stage == "generation_review":
        content = {
            "text_feedback": user_message,
            "next_revision_target": data.get("next_revision_target") or "lyrics",
            "next_revision_advice": data.get("next_revision_advice") or "",
            "keep": _as_list(data.get("keep")),
            "change": _as_list(data.get("change")),
            **source,
        }
        artifacts = [
            {
                "artifact_type": "generation_review",
                "title": f"{song.title} / AI 生成复盘",
                "summary": content["next_revision_advice"] or "AI 复盘下一轮修改方向。",
                "content": content,
                "is_recommended": True,
            }
        ]
        return assistant_message, artifacts, next_actions

    return None


def _diagnosis(song: Song, ep: EPState) -> tuple[str, list[dict], list[str]]:
    if _is_access_failure_song(song):
        biggest_problem = "需要把旧关系无法重新打开的概念压缩成可唱、可重复的短句，而不是解释设定。"
        strongest_material = ["access denied", "never try again", "可我停在你之外", song.title]
        risks = ["概念解释太多会不可唱", "错误提示过多会显得像旁白", "Style Prompt 如果写语言标签会污染 Suno 风格"]
        message = f"《{song.title}》在《{ep.title}》里承担旧关系/旧自我访问失败的节点。当前最该推进的是 Hook，而不是继续扩写设定。"
        next_actions = ["进入 Hook 实验室", "围绕 access denied 做短句测试"]
    else:
        material = _core_material(song)
        biggest_problem = "需要先把这首歌的核心画面、EP 功能和可重复 Hook 收束到同一个方向，避免直接跳到 Prompt 后生成发散。"
        strongest_material = [song.title, material, song.genre_direction or "待定风格", song.emotional_goal or "待定情绪"]
        risks = ["歌名和概念如果没有可唱短句，Suno 会把副歌生成得松散", "结构路线过早固定会让 EP 同质化", "风格词过多会稀释主唱和 Hook"]
        message = f"《{song.title}》当前最该先确认：它在《{ep.title}》里负责什么情绪转折，以及哪一句可以成为反复出现的 Hook。"
        next_actions = ["进入 Hook 实验室", "把歌名或核心画面压成 1-2 个短句"]
    content = {
        "ep_function": song.function_in_ep,
        "biggest_problem": biggest_problem,
        "strongest_material": strongest_material,
        "recommended_next_stage": "hook_lab",
        "risks": risks,
    }
    artifacts = [
        {
            "artifact_type": "diagnosis",
            "title": f"{song.title} / 歌曲诊断",
            "summary": "明确 EP 功能、最大问题和下一步。",
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, next_actions


def _hook_lab(song: Song) -> tuple[str, list[dict], list[str]]:
    if _is_access_failure_song(song):
        hook_goal = "短、重复、带访问失败和旧关系门外感"
        style_reference = "access denied / never try again"
    else:
        hook_goal = f"短、重复、可唱，围绕《{song.title}》和核心画面：{_core_material(song)}"
        style_reference = song.genre_direction or song.emotional_goal or song.title
    hooks = generate_hooks(song, hook_goal, style_reference, song.language_plan or "中文+English", 5)
    hook_dicts = [hook.model_dump() for hook in hooks]
    recommended = hook_dicts[0]["hook_text"] if hook_dicts else _short_hook_seed(song)
    content = {"hooks": hook_dicts, "recommended_hook": recommended}
    message = f"Hook 实验室给出 {len(hook_dicts)} 个短句方案。推荐先锁定 `{recommended}`，因为它最容易被 Suno 重复并记住。"
    artifacts = [
        {
            "artifact_type": "hook_set",
            "title": f"{song.title} / Hook 候选组",
            "summary": f"推荐 Hook：{recommended}",
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, ["接受 Hook 候选组", "锁定一个 Hook", "进入结构实验室"]


def _structure_lab(song: Song) -> tuple[str, list[dict], list[str]]:
    hook = _short_hook_seed(song)
    if _is_access_failure_song(song):
        recommended_route = "error_system"
        recommended_label = "错误系统路线"
    else:
        recommended_route = "classic_pop"
        recommended_label = "稳定主线路线"
    content = {
        "recommended_route": recommended_route,
        "routes": [
            {
                "route": "error_system",
                "label": "错误系统路线",
                "why": "这首歌的核心不是回忆，而是访问被拒绝；系统返回值可以成为段落推进器。",
                "section_map": [
                    {"section": "System Intro", "function": "建立失败提示声和冷感空间"},
                    {"section": "Cache Verse", "function": "旧聊天、旧房间、旧自己以碎片出现"},
                    {"section": "Retry Pre", "function": "缩短句子，模拟重复尝试"},
                    {"section": "Access Failure Chorus", "function": "短 Hook 重复，接可我停在你之外"},
                    {"section": "Old Version Bridge", "function": "半唱半说，承认旧版本无法打开"},
                    {"section": "Final Chorus", "function": "回到 Hook，不解决，只停住"},
                ],
                "hook_placement": ["Chorus first line", "Final Chorus first line", "Outro fragment"],
                "stability": 4,
                "innovation": 3,
                "suno_risks": ["标签过多会导致段落割裂", "错误提示词太多会变 spoken word"],
                "how_to_feed_suno": "用清晰段落标签，但每段说明控制在一两句。",
            },
            {
                "route": "loop_mantra",
                "label": "循环咒语路线",
                "why": "如果需要更实验，可以让 access denied 不断变形。",
                "section_map": [
                    {"section": "Loop A", "function": "低声重复 access denied"},
                    {"section": "Memory Insert", "function": "插入中文碎片"},
                    {"section": "Loop B", "function": "never try again 回答"},
                    {"section": "Exit", "function": "可我停在你之外 悬停"},
                ],
                "hook_placement": ["Every loop entrance"],
                "stability": 3,
                "innovation": 5,
                "suno_risks": ["可能生成得过散，需要更明确律动"],
                "how_to_feed_suno": "减少段落数量，强调 mantra-like repetition。",
            },
            {
                "route": "classic_pop",
                "label": "稳定主线路线",
                "why": "先让 Suno 把主歌、预副歌、副歌和桥段唱清楚，适合作为默认可执行版本。",
                "section_map": [
                    {"section": "Intro", "function": "建立律动和主音色，不抢 Hook"},
                    {"section": "Verse", "function": f"放入核心画面：{_core_material(song)}"},
                    {"section": "Pre-Chorus", "function": "缩短句子，把情绪推向副歌"},
                    {"section": "Chorus", "function": f"重复 Hook：{hook}"},
                    {"section": "Bridge", "function": "只放一个新角度，避免解释整首歌"},
                    {"section": "Final Chorus", "function": "回到 Hook，用叠唱或八度制造完成感"},
                ],
                "hook_placement": ["Chorus first line", "Final Chorus", "Outro tag"],
                "stability": 5,
                "innovation": 2,
                "suno_risks": ["过度稳定可能普通；需要用具体画面和音色区分"],
                "how_to_feed_suno": "段落标签清楚，描述短，优先保证副歌被唱出来。",
            },
            {
                "route": "contrast_turn",
                "label": "反差转向路线",
                "why": "如果需要结构创新，让主歌和副歌在密度、节奏或视角上发生明显转向，但仍保留一个稳定 Hook。",
                "section_map": [
                    {"section": "Cold Open", "function": "先露出 Hook 或一句核心碎片"},
                    {"section": "Verse A", "function": "低密度叙事，留白"},
                    {"section": "Chorus Pivot", "function": f"突然聚焦 Hook：{hook}"},
                    {"section": "Verse B", "function": "换一个视角或时间点"},
                    {"section": "Bridge / Breakdown", "function": "抽掉鼓或和声，制造反差"},
                    {"section": "Final Hook", "function": "只重复最有记忆点的一句"},
                ],
                "hook_placement": ["Cold Open", "Chorus Pivot", "Final Hook"],
                "stability": 3,
                "innovation": 4,
                "suno_risks": ["反差太多会让生成断裂；一次只改变一个维度"],
                "how_to_feed_suno": "明确 contrast 发生在 arrangement 或 vocal energy，不要同时改太多。",
            },
        ],
    }
    message = f"结构实验室推荐默认使用「{recommended_label}」。它先保证可执行；如果你要创新，可在同一张卡里改选实验路线，而不是把所有歌固定成同一套段落。"
    artifacts = [
        {
            "artifact_type": "structure_route",
            "title": f"{song.title} / 结构路线",
            "summary": f"推荐 {recommended_route}，并保留可选创新分支。",
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, ["接受结构路线", "生成歌词草稿", "需要更实验时切换 Loop-Mantra"]


def _lyrics_draft(song: Song) -> tuple[str, list[dict], list[str]]:
    hook = _short_hook_seed(song)
    if _is_access_failure_song(song):
        lyrics = f"""[System Intro]
access denied
never try again

[Verse]
我把旧对话重新打开
光标停在昨晚之前
你留下的句子没有坏
只是我没有权限

[Pre-Chorus]
我按下 retry
又按下撤回
门外的我
还在排队

[Chorus]
{hook}
{hook}
可我停在你之外
访问失败

[Bridge]
旧版本的我还亮着
像一盏不该亮的屏幕
我不是想回去
我只是想确认
那个人是否还在

[Final Chorus]
{hook}
never try again
可我停在你之外
访问失败

[Outro]
access denied
别让我关机"""
        summary = "围绕 access denied 与访问失败展开的可唱草稿。"
        message = "歌词草稿已经按错误系统路线展开：主歌放旧对话场景，副歌只服务 Hook，桥段承接 EP 核心主题。"
    else:
        image = _core_material(song)
        lyrics = f"""[Verse]
{image}
我把这一幕留到灯暗
有些话还没成形
先在呼吸里转弯

[Pre-Chorus]
别急着解释
别急着圆满
我只要一句
能被你听完

[Chorus]
{hook}
{hook}
如果世界太响
就让我重复这一行

[Bridge]
换一个角度看
我不是要答案
只是把快要散掉的光
重新放回手上

[Final Chorus]
{hook}
{hook}
这次不再绕远
让它落在心上"""
        summary = f"围绕「{hook}」展开的可唱草稿。"
        message = "歌词草稿已经先做成稳定可唱版本：主歌放画面，预副歌缩短，副歌只服务 Hook。后续可以在结构实验室切换创新路线。"
    quality = _score_lyrics_quality(song, lyrics, {"hook": hook})
    content = {
        "lyrics": lyrics,
        "hook": hook,
        "notes": "副歌保持短句；复杂概念放在主歌或桥段，避免让 Suno 把 Hook 唱成朗读。",
        "quality_score": quality["quality_score"],
        "quality_band": quality["quality_band"],
        "quality_passed": quality["quality_passed"],
        "quality_issues": quality["quality_issues"],
        "quality_strengths": quality["quality_strengths"],
    }
    artifacts = [
        {
            "artifact_type": "lyrics_draft",
            "title": f"{song.title} / 歌词草稿",
            "summary": summary,
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, ["接受歌词草稿", "进入 Suno Prompt 实验室"]


def _suno_prompt_lab(song: Song) -> tuple[str, list[dict], list[str]]:
    content = build_suno_prompt_packs(song)
    message = "已生成 3 套 Suno Prompt Pack：primary / alternate / experimental。推荐 primary，因为 Hook 位置最清楚，结构最稳。"
    artifacts = [
        {
            "artifact_type": "suno_prompt_pack",
            "title": f"{song.title} / Suno Prompt 包",
            "summary": "最多三套方案，推荐 primary。",
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, ["复制 primary 到 Suno", "生成后回到生成复盘记录结果"]


def _asset_organizer(song: Song) -> tuple[str, list[dict], list[str]]:
    content = {
        "bundle_items": ["song.md", "suno_prompt.md", "generation_reviews.md", "assets_manifest.json", "lyrics.txt", "notes_for_cubase.txt", "uploads/"],
        "cubase_note": "V1 只整理素材和导入说明，不生成 Cubase 原生工程。",
    }
    message = "素材整理阶段会把当前歌词、Prompt、复盘和上传文件打包成制作资料包。"
    artifacts = [
        {
            "artifact_type": "asset_bundle",
            "title": f"{song.title} / 素材整理计划",
            "summary": "准备导出制作资料包。",
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, ["上传 Suno 文件", "导出素材包"]


def build_stage_output(song: Song, ep: EPState, stage: str) -> tuple[str, list[dict], list[str]]:
    if stage == "diagnosis":
        return _diagnosis(song, ep)
    if stage == "hook_lab":
        return _hook_lab(song)
    if stage == "structure_lab":
        return _structure_lab(song)
    if stage == "lyrics_draft":
        return _lyrics_draft(song)
    if stage == "suno_prompt_lab":
        return _suno_prompt_lab(song)
    if stage == "asset_organizer":
        return _asset_organizer(song)
    return (
        "生成复盘需要你记录 Suno 听感、评分和上传素材；系统会基于这些文本反馈给下一轮修正建议。",
        [],
        ["填写生成复盘表", "上传相关音频或 MIDI"],
    )


def _mark_fallback(artifact_payloads: list[dict]) -> None:
    for payload in artifact_payloads:
        payload.setdefault("content", {})
        payload["content"].setdefault("source", "local_fallback")
        payload["content"].setdefault("fallback", True)


async def build_stage_output_with_ai(
    song: Song,
    ep: EPState,
    stage: str,
    user_goal: str,
    user_message: str,
) -> tuple[str, list[dict], list[str]]:
    ai_output = await _try_ai_stage(song, ep, stage, user_goal, user_message)
    if ai_output:
        return ai_output

    message, artifact_payloads, next_actions = build_stage_output(song, ep, stage)
    _mark_fallback(artifact_payloads)
    if stage in {"diagnosis", "hook_lab", "structure_lab", "lyrics_draft", "generation_review"}:
        message = f"AI 本阶段生成不可用，已临时使用本地规则草稿。\n\n{message}"
    return message, artifact_payloads, next_actions


async def build_generation_review_with_ai(
    song: Song,
    ep: EPState,
    feedback_context: dict,
) -> dict | None:
    result = await _try_ai_stage(
        song,
        ep,
        "generation_review",
        "根据 Suno 生成结果决定下一轮修改优先级",
        json.dumps(feedback_context, ensure_ascii=False),
    )
    if not result:
        return None
    _, artifact_payloads, _ = result
    return artifact_payloads[0] if artifact_payloads else None


async def create_session_with_artifacts(
    db: Session,
    song: Song,
    ep: EPState,
    stage: str,
    mode: str,
    output_mode: str,
    user_goal: str,
    user_message: str,
) -> CreativeSession:
    message, artifact_payloads, next_actions = await build_stage_output_with_ai(song, ep, stage, user_goal, user_message)
    session = CreativeSession(
        song_id=song.id,
        stage=stage,
        mode=mode,
        output_mode=output_mode,
        user_goal=user_goal,
        user_message=user_message,
        assistant_message=message,
        stage_recommendation={
            "current_stage": stage,
            "next_stage": next_stage(stage),
            "reason": "本阶段已产出待确认 Artifact，接受后建议进入下一阶段。",
            "requires_user_confirmation": True,
        },
        next_actions=next_actions,
    )
    db.add(session)
    db.flush()

    for payload in artifact_payloads:
        db.add(
            CreativeArtifact(
                song_id=song.id,
                session_id=session.id,
                artifact_type=payload["artifact_type"],
                title=payload["title"],
                summary=payload["summary"],
                content=payload["content"],
                is_recommended=payload.get("is_recommended", False),
            )
        )
    song.stage_status = "in_progress"
    db.flush()
    db.refresh(session)
    return session
