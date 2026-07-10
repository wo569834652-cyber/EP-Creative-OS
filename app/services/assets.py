import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AssetFile, CreativeArtifact, Song


STORAGE_ROOT = Path("storage")


def safe_filename(filename: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)[:180] or "asset"


async def store_upload(db: Session, song: Song, upload: UploadFile, role: str = "other") -> AssetFile:
    content = await upload.read()
    digest = hashlib.sha256(content).hexdigest()
    filename = safe_filename(upload.filename or "upload.bin")
    folder = STORAGE_ROOT / "imports" / str(song.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest[:12]}_{filename}"
    path.write_bytes(content)

    suffix = Path(filename).suffix.lower().lstrip(".")
    asset = AssetFile(
        song_id=song.id,
        filename=filename,
        stored_path=str(path),
        file_type=suffix,
        mime_type=upload.content_type or "",
        size_bytes=len(content),
        sha256=digest,
        role=role,
        metadata_json={"source": "user_upload"},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _artifact_markdown(artifact: CreativeArtifact) -> str:
    return f"## {artifact.title}\n\n{artifact.summary}\n\n```json\n{json.dumps(artifact.content, ensure_ascii=False, indent=2)}\n```\n"


def _prompt_pack_markdown(artifact: CreativeArtifact) -> str:
    content = artifact.content or {}
    recommended = content.get("recommended_pack") or {}
    if not recommended and content.get("packs"):
        recommended = next((pack for pack in content["packs"] if pack.get("recommended")), content["packs"][0])
    if not recommended:
        return _artifact_markdown(artifact)
    validation = recommended.get("validation") or {}
    settings = recommended.get("advanced_settings") or {}
    return f"""## {artifact.title}

{artifact.summary}

### Recommended Variant

{recommended.get("variant", "")} / {recommended.get("variant_role", "")}

Reason: {recommended.get("recommendation_reason", "")}

### Music Spec

```json
{json.dumps(recommended.get("music_spec") or {}, ensure_ascii=False, indent=2)}
```

### Style Prompt

{recommended.get("style_prompt", "")}

### Lyrics Prompt

{recommended.get("lyrics_prompt", "")}

### Exclude Prompt

{recommended.get("exclude_prompt", "")}

### Advanced Settings

- Weirdness: {settings.get("weirdness")}
- Style Influence: {settings.get("style_influence")}
- Audio Influence: {settings.get("audio_influence")}

### Validation Summary

- Score: {validation.get("score")}
- Passed Checks: {", ".join(validation.get("passed_checks", []) or []) or "none"}
- Warnings: {", ".join(validation.get("warnings", []) or []) or "none"}
- Blocking Issues: {", ".join(validation.get("blocking_issues", []) or []) or "none"}

### Revision Strategy

{recommended.get("revision_strategy", "")}

### Source Trace

```json
{json.dumps(recommended.get("source_trace") or {}, ensure_ascii=False, indent=2)}
```

### Route Spec

```json
{json.dumps(recommended.get("route_spec") or {}, ensure_ascii=False, indent=2)}
```

### Feedback Summary

```json
{json.dumps(content.get("feedback_summary") or recommended.get("feedback_summary") or {}, ensure_ascii=False, indent=2)}
```
"""


def _selected_prompt_artifacts(song: Song, artifacts: list[CreativeArtifact]) -> list[CreativeArtifact]:
    prompt_artifacts = [a for a in artifacts if a.artifact_type == "suno_prompt_pack"]
    if not prompt_artifacts:
        return []
    selected: list[CreativeArtifact] = []
    if song.current_prompt_pack_id:
        selected = [a for a in prompt_artifacts if a.id == song.current_prompt_pack_id]
    if not selected:
        selected = [a for a in prompt_artifacts if a.status == "accepted"]
    if not selected:
        selected = prompt_artifacts[-1:]
    return selected


def create_asset_bundle(db: Session, song: Song) -> Path:
    artifacts = list(
        db.scalars(
            select(CreativeArtifact)
            .where(CreativeArtifact.song_id == song.id)
            .where(CreativeArtifact.status == "accepted")
            .order_by(CreativeArtifact.created_at)
        ).all()
    )
    assets = list(db.scalars(select(AssetFile).where(AssetFile.song_id == song.id).order_by(AssetFile.created_at)).all())

    export_dir = STORAGE_ROOT / "exports" / str(song.id)
    export_dir.mkdir(parents=True, exist_ok=True)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{song.id}_asset_bundle.zip", dir=export_dir)
    temp.close()
    path = Path(temp.name)

    prompt_artifacts = _selected_prompt_artifacts(song, artifacts)
    review_artifacts = [a for a in artifacts if a.artifact_type == "generation_review"]

    song_md = f"""# {song.title}

## Current State

- Current stage: {song.current_stage}
- Locked hook: {song.locked_hook or "not locked"}
- Structure route: {song.current_structure_route or "not selected"}
- BPM: {song.bpm}
- Genre direction: {song.genre_direction}

## EP Function

{song.function_in_ep}

## Concept

{song.concept}
"""
    suno_md = "\n\n".join(_prompt_pack_markdown(a) for a in prompt_artifacts) or "No accepted Suno Prompt Pack yet."
    reviews_md = "\n\n".join(_artifact_markdown(a) for a in review_artifacts) or "No generation reviews yet."
    manifest = [
        {
            "id": asset.id,
            "filename": asset.filename,
            "role": asset.role,
            "size_bytes": asset.size_bytes,
            "sha256": asset.sha256,
            "file_type": asset.file_type,
        }
        for asset in assets
    ]
    notes = f"""# Cubase Notes for {song.title}

V1 organizes production assets and does not generate a native Cubase project.

Suggested workflow:
1. Create a new Cubase project and set BPM to {song.bpm}.
2. Import downloaded Suno audio or MIDI.
3. Use song.md for song context and suno_prompt.md for prompt, section, validation, and revision notes.
4. Align audio manually to bar 1 and keep future production notes in EP Creative OS generation reviews.
"""

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("song.md", song_md)
        zf.writestr("suno_prompt.md", suno_md)
        zf.writestr("generation_reviews.md", reviews_md)
        zf.writestr("assets_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("lyrics.txt", song.lyrics or "")
        zf.writestr("notes_for_cubase.txt", notes)
        for asset in assets:
            source = Path(asset.stored_path)
            if source.exists():
                zf.write(source, f"uploads/{asset.id}_{asset.sha256[:8]}_{asset.filename}")

    return path
