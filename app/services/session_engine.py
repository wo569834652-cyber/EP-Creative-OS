from sqlalchemy.orm import Session

from app.models import CreativeArtifact, CreativeSession, EPState, Song
from app.services.hooks import generate_hooks
from app.services.stages import next_stage
from app.services.suno_engine import build_suno_prompt_packs


def _diagnosis(song: Song, ep: EPState) -> tuple[str, list[dict], list[str]]:
    content = {
        "ep_function": song.function_in_ep,
        "biggest_problem": "需要把旧关系无法重新打开的概念压缩成可唱、可重复的短句，而不是解释设定。",
        "strongest_material": ["access denied", "never try again", "可我停在你之外", song.title],
        "recommended_next_stage": "hook_lab",
        "risks": ["概念解释太多会不可唱", "错误提示过多会显得像旁白", "Style Prompt 如果写语言标签会污染 Suno 风格"],
    }
    message = f"《{song.title}》在《{ep.title}》里承担旧关系/旧自我访问失败的节点。当前最该推进的是 Hook，而不是继续扩写设定。"
    artifacts = [
        {
            "artifact_type": "diagnosis",
            "title": f"{song.title} / 歌曲诊断",
            "summary": "明确 EP 功能、最大问题和下一步。",
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, ["进入 Hook 实验室", "围绕 access denied 做短句测试"]


def _hook_lab(song: Song) -> tuple[str, list[dict], list[str]]:
    hooks = generate_hooks(song, "短、重复、带访问失败和旧关系门外感", "access denied / never try again", "中文+English", 5)
    hook_dicts = [hook.model_dump() for hook in hooks]
    recommended = hook_dicts[0]["hook_text"] if hook_dicts else "access denied"
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
    content = {
        "recommended_route": "error_system",
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
        ],
    }
    message = "结构实验室推荐默认使用错误系统路线，既能保留概念锋利度，也比纯实验结构更容易让 Suno 执行。"
    artifacts = [
        {
            "artifact_type": "structure_route",
            "title": f"{song.title} / 结构路线",
            "summary": "推荐 Error-System Route，并保留 Loop-Mantra 实验分支。",
            "content": content,
            "is_recommended": True,
        }
    ]
    return message, artifacts, ["接受结构路线", "生成歌词草稿", "需要更实验时切换 Loop-Mantra"]


def _lyrics_draft(song: Song) -> tuple[str, list[dict], list[str]]:
    hook = song.locked_hook or "access denied"
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
    content = {"lyrics": lyrics, "hook": hook, "notes": "副歌保持短句，复杂概念放在 Bridge。"}
    message = "歌词草稿已经按错误系统路线展开：主歌放旧对话场景，副歌只服务 Hook，桥段承接 EP 核心主题。"
    artifacts = [
        {
            "artifact_type": "lyrics_draft",
            "title": f"{song.title} / 歌词草稿",
            "summary": "围绕 access denied 与访问失败展开的可唱草稿。",
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


def create_session_with_artifacts(
    db: Session,
    song: Song,
    ep: EPState,
    stage: str,
    mode: str,
    output_mode: str,
    user_goal: str,
    user_message: str,
) -> CreativeSession:
    message, artifact_payloads, next_actions = build_stage_output(song, ep, stage)
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
