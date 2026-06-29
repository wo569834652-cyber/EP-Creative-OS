import json
from difflib import unified_diff

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CreativeArtifact, Song, SongVersion


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
    "current_stage",
    "stage_status",
    "locked_hook",
    "current_structure_route",
    "current_prompt_pack_id",
]


def song_snapshot(song: Song) -> dict:
    return {field: getattr(song, field) for field in VERSION_FIELDS}


def detect_change_type(before: dict, after: dict) -> str:
    changed = {key for key in VERSION_FIELDS if before.get(key) != after.get(key)}
    if not changed:
        return "full"
    if changed <= {"lyrics"}:
        return "lyrics"
    if changed <= {"style_prompt", "lyrics_prompt", "genre_direction", "bpm", "current_prompt_pack_id"}:
        return "suno_prompt"
    if changed <= {"locked_hook"}:
        return "hook"
    if changed <= {"current_structure_route"}:
        return "structure"
    if changed <= {"concept", "function_in_ep", "emotional_goal", "notes", "language_plan"}:
        return "diagnosis"
    return "full"


def next_version_number(db: Session, song_id: int) -> int:
    current_max = db.scalar(select(func.max(SongVersion.version_number)).where(SongVersion.song_id == song_id))
    return (current_max or 0) + 1


def create_version(
    db: Session,
    song: Song,
    change_type: str,
    change_summary: str,
    artifact_ids: list[int] | None = None,
    session_id: int | None = None,
    locked: bool = False,
) -> SongVersion:
    version = SongVersion(
        song_id=song.id,
        session_id=session_id,
        version_number=next_version_number(db, song.id),
        version_label=f"v{next_version_number(db, song.id)} - {change_summary[:48]}",
        change_type=change_type,
        artifact_ids=artifact_ids or [],
        content_snapshot=song_snapshot(song),
        summary=change_summary,
        change_summary=change_summary,
        locked=locked,
    )
    db.add(version)
    db.flush()
    return version


def create_version_from_artifact(db: Session, artifact: CreativeArtifact) -> SongVersion:
    song = artifact.song
    summary = f"接受 {artifact.title}"
    if artifact.artifact_type == "hook_set":
        recommended = artifact.content.get("recommended_hook") or artifact.content.get("hooks", [{}])[0].get("hook_text", "")
        song.locked_hook = recommended or song.locked_hook
    elif artifact.artifact_type == "structure_route":
        song.current_structure_route = artifact.content.get("recommended_route", song.current_structure_route)
    elif artifact.artifact_type == "suno_prompt_pack":
        song.current_prompt_pack_id = artifact.id
        recommended = artifact.content.get("recommended_pack", {})
        song.style_prompt = recommended.get("style_prompt", song.style_prompt)
        song.lyrics_prompt = recommended.get("lyrics_prompt", song.lyrics_prompt)
    elif artifact.artifact_type == "lyrics_draft":
        song.lyrics = artifact.content.get("lyrics", song.lyrics)
    return create_version(
        db,
        song,
        artifact.artifact_type,
        summary,
        artifact_ids=[artifact.id],
        session_id=artifact.session_id,
        locked=artifact.locked,
    )


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
