from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EPState, Song


def seed_database(db: Session) -> None:
    existing_ep = db.scalar(select(EPState).limit(1))
    if existing_ep:
        return

    ep = EPState(
        title="GROWING UP.EXE",
        one_liner="一张关于成年人精神残影的卧室概念 EP",
        core_theme="不是回到过去，而是确认旧版本的自己是否还活着",
        world_view="城市日常像一套后台系统：通勤、屏幕、旧聊天记录、猫、雨声共同组成精神桌面。",
        emotional_keywords=["疲惫", "残影", "延迟", "亲密", "待机", "自我检索"],
        aesthetic_keywords=["bedroom pop", "CRT glow", "office liminal", "late night subway", "lo-fi system UI"],
        sonic_layers={
            "reality": ["office", "subway", "elevator", "rain", "apartment room tone"],
            "machine": ["old computer fan", "CRT hum", "system alert", "MIDI-like fragments"],
            "body": ["breath", "close vocal", "silence", "hesitation", "cat sounds"],
        },
        narrative_arc="从现实入口进入后台进程，穿过旧关系和创作检索，最后停在不关机的待机状态。",
        song_list=[
            "今天也正常下班",
            "GROWING UP.EXE",
            "But My Body Knows",
            "访问失败",
            "没人听",
            "加载太久了",
            "别关掉",
        ],
    )
    db.add(ep)
    db.flush()

    songs = [
        {
            "title": "今天也正常下班",
            "function_in_ep": "现实入口，通勤烦躁，回家但精神未返回",
            "concept": "下班不是休息，而是系统把身体送回家，意识还留在电梯和地铁里。",
            "emotional_goal": "低电量、麻木、微弱自嘲",
            "bpm": 92,
            "genre_direction": "bedroom pop / lo-fi electronic",
            "language_plan": "中文主唱，少量英文系统短语作为背景人声",
        },
        {
            "title": "GROWING UP.EXE",
            "function_in_ep": "主程序，成长作为后台进程",
            "concept": "成长不是一个仪式，而是无法关闭的后台程序。",
            "emotional_goal": "克制、疑问、带一点系统错误的宿命感",
            "bpm": 98,
            "genre_direction": "alt pop / glitchy synth pop",
            "language_plan": "中文主唱，Hook 可混入英文文件名感短句",
            "notes": "hook reference: 我听见回音 / 却忘了原因",
        },
        {
            "title": "But My Body Knows",
            "function_in_ep": "现代城市亲密关系，不说永远但身体诚实",
            "concept": "关系不再许诺永远，但身体记得靠近、退后、沉默的顺序。",
            "emotional_goal": "暧昧、诚实、夜间亲密",
            "bpm": 86,
            "genre_direction": "alternative pop R&B / moody pop",
            "language_plan": "英文标题与副歌，中文 Verse，少量日语气声点缀",
        },
        {
            "title": "访问失败",
            "function_in_ep": "旧对话、旧关系、旧自己无法重新打开",
            "concept": "尝试访问旧关系和旧自己，系统返回拒绝，但人还停在门外。",
            "emotional_goal": "冷、卡住、旧伤口不戏剧化",
            "bpm": 88,
            "genre_direction": "minimal alt pop / electronic ballad",
            "language_plan": "中文主歌，英文错误提示作为 Hook",
            "notes": "hook reference:\naccess denied\nnever try again\n可我停在你之外\n访问失败",
        },
        {
            "title": "没人听",
            "function_in_ep": "创作作为检索，没人听但仍然播放",
            "concept": "播放量不是存在证明，写歌像在空硬盘里检索自己。",
            "emotional_goal": "孤独但不卖惨，固执继续播放",
            "bpm": 94,
            "genre_direction": "indie pop / tape-warped synth",
            "language_plan": "中文为主，英文只作为界面词",
        },
        {
            "title": "加载太久了",
            "function_in_ep": "现实锚点，猫和陪伴，不需要知道过去",
            "concept": "不是所有陪伴都需要解释来历，有些温度只负责把你留在现在。",
            "emotional_goal": "温柔、生活感、轻微释然",
            "bpm": 90,
            "genre_direction": "warm bedroom pop / soft R&B",
            "language_plan": "中文主唱，可加入轻声拟声与短日语",
        },
        {
            "title": "别关掉",
            "function_in_ep": "结尾，待机，不是解决，是不要终止",
            "concept": "结尾不是治愈，而是保留电源，让明天还有重新打开的可能。",
            "emotional_goal": "安静、悬而未决、留灯",
            "bpm": 76,
            "genre_direction": "ambient pop / slow electronic",
            "language_plan": "中文极简句，英文系统短句作为尾声",
        },
    ]

    for song_data in songs:
        db.add(Song(ep_id=ep.id, **song_data))

    db.commit()
