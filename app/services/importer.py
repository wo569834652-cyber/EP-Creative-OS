from pathlib import Path

from fastapi import UploadFile
from mido import MidiFile, tempo2bpm
from sqlalchemy.orm import Session

from app.models import ImportedAsset


ALLOWED_EXTENSIONS = {".mid", ".midi", ".wav", ".mp3"}


async def import_suno_file(db: Session, upload: UploadFile) -> ImportedAsset:
    filename = upload.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Only .mid, .midi, .wav, and .mp3 files are supported.")

    content = await upload.read()
    metadata: dict = {"size_bytes": len(content)}

    if suffix in {".mid", ".midi"}:
        mid = MidiFile(file=__import__("io").BytesIO(content))
        note_count = 0
        tempos: list[int] = []
        track_names: list[str] = []
        for track in mid.tracks:
            current_name = ""
            for msg in track:
                if msg.type == "track_name":
                    current_name = msg.name
                elif msg.type == "set_tempo":
                    tempos.append(round(tempo2bpm(msg.tempo)))
                elif msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
                    note_count += 1
            track_names.append(current_name or f"Track {len(track_names) + 1}")
        metadata.update(
            {
                "tempo": tempos[0] if tempos else None,
                "tempos": tempos,
                "tracks": track_names,
                "track_count": len(mid.tracks),
                "note_count": note_count,
                "ticks_per_beat": mid.ticks_per_beat,
            }
        )
    else:
        metadata.update({"analysis": "Audio metadata saved only; waveform analysis is out of scope for MVP."})

    asset = ImportedAsset(filename=filename, file_type=suffix.lstrip("."), metadata_json=metadata)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
