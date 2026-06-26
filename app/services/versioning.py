import json
from difflib import unified_diff

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Song, SongVersion


VERSION_FIELDS = [
    "title",
    "function_in_ep",
    "concept",
    "emotional_goal",
    "bpm",
    "genre_direction",
    "language_plan",
    "lyrics",
    "style_prompt",
    "lyrics_prompt",
    "notes",
]


def song_snapshot(song: Song) -> dict:
    return {field: getattr(song, field) for field in VERSION_FIELDS}


def detect_change_type(before: dict, after: dict) -> str:
    changed = {key for key in VERSION_FIELDS if before.get(key) != after.get(key)}
    if not changed:
        return "full"
    if changed <= {"lyrics"}:
        return "lyrics"
    if changed <= {"style_prompt", "lyrics_prompt", "genre_direction", "bpm"}:
        return "style"
    if changed <= {"concept", "function_in_ep", "emotional_goal", "notes", "language_plan"}:
        return "concept"
    return "full"


def create_version(db: Session, song: Song, change_type: str, change_summary: str) -> SongVersion:
    current_max = db.scalar(
        select(func.max(SongVersion.version_number)).where(SongVersion.song_id == song.id)
    )
    version = SongVersion(
        song_id=song.id,
        version_number=(current_max or 0) + 1,
        change_type=change_type,
        content_snapshot=song_snapshot(song),
        change_summary=change_summary,
    )
    db.add(version)
    db.flush()
    return version


def snapshot_diff(from_version: SongVersion, to_version: SongVersion) -> str:
    left = json.dumps(from_version.content_snapshot, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    right = json.dumps(to_version.content_snapshot, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    return "\n".join(
        unified_diff(
            left,
            right,
            fromfile=f"version_{from_version.version_number}",
            tofile=f"version_{to_version.version_number}",
            lineterm="",
        )
    )
