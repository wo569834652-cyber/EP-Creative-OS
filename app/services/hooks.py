from app.models import Song
from app.schemas import HookOption


def _score_hook(text: str) -> int:
    compact = text.replace(" ", "")
    length_bonus = 24 if len(compact) <= 10 else 14 if len(compact) <= 18 else 4
    repeat_bonus = 18 if any(compact.count(ch) >= 2 for ch in set(compact)) else 8
    vowel_bonus = 12 if compact[-1:] in "aeiouaoeiuvnんういあえお" else 6
    prose_penalty = 18 if len(compact) > 28 or "因为" in compact or "所以" in compact else 0
    score = 52 + length_bonus + repeat_bonus + vowel_bonus - prose_penalty
    return max(1, min(100, score))


def generate_hooks(song: Song, hook_goal: str, style_reference: str | None, language_mix: str | None, count: int) -> list[HookOption]:
    base_fragments = [
        "别关掉我",
        "还在后台",
        "access denied",
        "never try again",
        "我听见回音",
        "忘了原因",
        "loading too long",
        "没人听见",
        "身体知道",
        "正常下班",
        "まだここにいる",
        "ログアウトしないで",
    ]

    title_hint = song.title.strip()
    if title_hint and title_hint not in base_fragments:
        base_fragments.insert(0, title_hint)

    goal_words = [word.strip("，。,.!? ") for word in hook_goal.split() if word.strip("，。,.!? ")]
    if goal_words:
        base_fragments.extend(goal_words[:3])

    options: list[HookOption] = []
    seen: set[str] = set()
    for idx, fragment in enumerate(base_fragments):
        if not fragment or fragment in seen:
            continue
        seen.add(fragment)
        text = fragment
        if idx % 3 == 1 and len(fragment) <= 12:
            text = f"{fragment} / {fragment}"
        elif idx % 3 == 2 and style_reference:
            text = f"{fragment}, {style_reference.split('/')[0].strip()}"

        score = _score_hook(text)
        options.append(
            HookOption(
                hook_text=text,
                why_it_works="短句可重复，能直接放在副歌或 post-chorus；概念不解释完，给旋律留空间。",
                rhythm_notes="建议落在 2 小节循环里，第一遍低声进入，第二遍加叠唱或 octave double。",
                suno_risk="如果附带太多叙事词，Suno 可能把 Hook 唱成朗读；保持短句和重复更稳。",
                score=score,
            )
        )
        if len(options) >= count:
            break

    if language_mix and "hiragana" in language_mix.lower() and len(options) < count:
        options.append(
            HookOption(
                hook_text="まだ きえない",
                why_it_works="hiragana_only 的柔软质感适合做尾音延长，和系统感标题形成反差。",
                rhythm_notes="每个 mora 分开落拍，末尾拖长到下一小节。",
                suno_risk="日语片段要少量使用，否则会把整首歌的语言重心带偏。",
                score=86,
            )
        )

    return sorted(options, key=lambda item: item.score, reverse=True)[:count]
