from sqlalchemy.orm import Session

from app.models import CreativeArtifact, CreativeSession, EPState, Song
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
    content = {"lyrics": lyrics, "hook": hook, "notes": "副歌保持短句；复杂概念放在主歌或桥段，避免让 Suno 把 Hook 唱成朗读。"}
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
