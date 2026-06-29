import hashlib
import json
import shutil
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


def create_asset_bundle(db: Session, song: Song) -> Path:
    artifacts = list(
        db.scalars(
            select(CreativeArtifact)
            .where(CreativeArtifact.song_id == song.id)
            .where(CreativeArtifact.status.in_(["accepted", "pending"]))
            .order_by(CreativeArtifact.created_at)
        ).all()
    )
    assets = list(db.scalars(select(AssetFile).where(AssetFile.song_id == song.id).order_by(AssetFile.created_at)).all())

    export_dir = STORAGE_ROOT / "exports" / str(song.id)
    export_dir.mkdir(parents=True, exist_ok=True)
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{song.id}_asset_bundle.zip", dir=export_dir)
    temp.close()
    path = Path(temp.name)

    prompt_artifacts = [a for a in artifacts if a.artifact_type == "suno_prompt_pack"]
    review_artifacts = [a for a in artifacts if a.artifact_type == "generation_review"]

    song_md = f"""# {song.title}

## 当前状态

- 当前阶段：{song.current_stage}
- 锁定 Hook：{song.locked_hook or "未锁定"}
- 结构路线：{song.current_structure_route or "未选择"}
- BPM：{song.bpm}
- 风格方向：{song.genre_direction}

## EP 功能

{song.function_in_ep}

## 概念

{song.concept}
"""
    suno_md = "\n\n".join(_artifact_markdown(a) for a in prompt_artifacts) or "尚未接受 Suno Prompt Pack。"
    reviews_md = "\n\n".join(_artifact_markdown(a) for a in review_artifacts) or "尚未记录生成复盘。"
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

V1 只提供素材整理，不生成 Cubase 原生工程。

建议：
1. 在 Cubase 中新建工程，设置 BPM 为 {song.bpm}。
2. 导入 Suno 下载的音频或 MIDI。
3. 参考 song.md 的结构路线和 suno_prompt.md 的段落提示。
4. 手动对齐音频起点和小节线。
5. 将后续制作备注继续写回 EP Creative OS 的生成复盘。
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
                zf.write(source, f"uploads/{asset.filename}")

    return path
