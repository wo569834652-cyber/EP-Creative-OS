import hashlib
import re

from app.models import Song
from app.schemas import HookOption


def _compact_text(value: str | None, limit: int = 14) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    text = re.sub(r"[，。！？、,.!?;；:：\"'“”‘’《》()\[\]{}]+", " ", text).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].strip()


def _core_tokens(song: Song) -> list[str]:
    raw = " ".join(
        [
            song.title or "",
            song.concept or "",
            song.function_in_ep or "",
            song.emotional_goal or "",
            song.genre_direction or "",
        ]
    )
    tokens = []
    for part in re.split(r"[\s,，。！？、/\\|;；:：()\[\]{}<>《》\"'“”‘’]+", raw):
        part = part.strip()
        if len(part) >= 2 and part not in tokens:
            tokens.append(part)
    return tokens[:10]


def _score_hook(text: str, innovation: int = 1) -> int:
    compact = text.replace(" ", "")
    length_bonus = 24 if len(compact) <= 10 else 16 if len(compact) <= 18 else 5
    repeat_bonus = 18 if any(compact.count(ch) >= 2 for ch in set(compact)) else 8
    slash_bonus = 6 if "/" in text else 0
    prose_penalty = 20 if len(compact) > 30 or "因为" in compact or "所以" in compact else 0
    innovation_penalty = max(0, innovation - 3) * 3
    score = 50 + length_bonus + repeat_bonus + slash_bonus - prose_penalty - innovation_penalty
    return max(1, min(100, score))


def _option(
    hook_text: str,
    version_label: str,
    angle: str,
    innovation: int,
    use_case: str,
    rhythm_notes: str,
    suno_risk: str,
) -> HookOption:
    return HookOption(
        hook_text=hook_text,
        version_label=version_label,
        angle=angle,
        innovation=innovation,
        use_case=use_case,
        why_it_works=f"{angle}。它不是解释概念，而是给副歌一个可重复的短句锚点。",
        rhythm_notes=rhythm_notes,
        suno_risk=suno_risk,
        score=_score_hook(hook_text, innovation),
    )


def _dedupe_and_avoid(options: list[HookOption], avoid_hooks: list[str], count: int, seed: str) -> list[HookOption]:
    avoid = {item.strip().lower() for item in avoid_hooks if item and item.strip()}
    seen: set[str] = set()
    fresh: list[HookOption] = []
    recycled: list[HookOption] = []
    offset = int(hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:4], 16) % max(1, len(options))
    rotated = options[offset:] + options[:offset]
    for option in rotated:
        key = option.hook_text.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if key in avoid:
            recycled.append(option)
        else:
            fresh.append(option)
    picked = fresh[:count]
    if len(picked) < count:
        picked.extend(recycled[: count - len(picked)])
    return sorted(picked, key=lambda item: (item.score, item.innovation), reverse=True)[:count]


def generate_hooks(
    song: Song,
    hook_goal: str,
    style_reference: str | None,
    language_mix: str | None,
    count: int,
    avoid_hooks: list[str] | None = None,
    variation_seed: str = "",
) -> list[HookOption]:
    tokens = _core_tokens(song)
    title = _compact_text(song.title, 12) or "别停下"
    image = _compact_text(song.concept or song.function_in_ep or song.emotional_goal, 12) or title
    emotion = _compact_text(song.emotional_goal, 10) or "还没结束"
    style = _compact_text(style_reference, 14)

    base_options = [
        _option(
            hook_text=title,
            version_label="A 稳定主线",
            angle="直接把歌名压成副歌口号",
            innovation=1,
            use_case="默认可执行版本，适合先测旋律和记忆点。",
            rhythm_notes="两小节内重复，第一遍轻，第二遍加叠唱。",
            suno_risk="如果歌名偏长，需要再切短，否则副歌会像一句说明。",
        ),
        _option(
            hook_text=f"{title} / {title}",
            version_label="B 重复咒语",
            angle="用重复制造记忆点",
            innovation=2,
            use_case="适合 bedroom pop、lo-fi、轻电子里的 post-chorus。",
            rhythm_notes="把斜杠前后分成两次呼吸，第二次可上三度或八度。",
            suno_risk="重复太满会占掉主歌空间，Lyrics Prompt 要留空拍。",
        ),
        _option(
            hook_text=f"别把{image}关掉",
            version_label="C 画面钩子",
            angle="把核心画面变成动作请求",
            innovation=3,
            use_case="适合需要让概念更具体、更像一句歌词的版本。",
            rhythm_notes="前半句低声进入，最后两个字拉长。",
            suno_risk="如果画面词太抽象，Suno 会唱得像旁白。",
        ),
        _option(
            hook_text=f"我还在{image}",
            version_label="D 角色独白",
            angle="从人物状态出发，不直接复述诊断结论",
            innovation=3,
            use_case="适合主歌已经很叙事、副歌需要情绪落点的版本。",
            rhythm_notes="弱起进入，落在最后一个名词上。",
            suno_risk="需要避免后面继续解释，否则 Hook 会变散。",
        ),
        _option(
            hook_text=f"{emotion} / 别叫醒我",
            version_label="E 情绪反转",
            angle="让情绪词和行动短句形成轻微反差",
            innovation=4,
            use_case="适合需要一点新鲜感，但仍能让 Suno 唱清楚的版本。",
            rhythm_notes="第一句半唱，第二句更短更贴近耳语。",
            suno_risk="创新度较高，最好只在副歌或 outro 使用。",
        ),
        _option(
            hook_text="still loading",
            version_label="F 英文纹理",
            angle="把系统感变成声音纹理",
            innovation=4,
            use_case="适合电子、alt-pop 或需要一点界面感的段落。",
            rhythm_notes="四拍内短促重复，可作为背景 ad-lib。",
            suno_risk="不要把语言标签写进 Style Prompt，只把这句放进 Lyrics Prompt。",
        ),
    ]

    if "access" in " ".join(tokens).lower() or "访问" in " ".join(tokens):
        base_options.extend(
            [
                _option(
                    hook_text="access denied",
                    version_label="G 系统错误",
                    angle="把错误提示当作副歌记忆点",
                    innovation=3,
                    use_case="适合《访问失败》这种系统隐喻明确的歌。",
                    rhythm_notes="短促进入，第二遍用低八度或 whisper double。",
                    suno_risk="不要堆太多错误提示，否则会变成 spoken word。",
                ),
                _option(
                    hook_text="never try again",
                    version_label="H 冷回答",
                    angle="用系统式拒绝回应人的请求",
                    innovation=4,
                    use_case="适合桥段或 final chorus 的反向回答。",
                    rhythm_notes="每个词分开落拍，尾音不要拖太满。",
                    suno_risk="英文过多可能抢走中文主线，只作为对照版本。",
                ),
            ]
        )

    if language_mix and "hiragana" in language_mix.lower():
        base_options.append(
            _option(
                hook_text="まだ 消えない",
                version_label="I 日文尾音",
                angle="用柔软尾音做 outro 版本",
                innovation=5,
                use_case="只适合少量点缀，不适合作为默认主 Hook。",
                rhythm_notes="mora 分开落拍，最后一拍留气口。",
                suno_risk="语言重心可能被带偏，必须作为可选实验。",
            )
        )

    seed = "|".join([song.title or "", hook_goal or "", style_reference or "", variation_seed or "", ",".join(avoid_hooks or [])])
    return _dedupe_and_avoid(base_options, avoid_hooks or [], count, seed)
