import csv
import io
import json
import tempfile
import zipfile
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreativeArtifact, Song
from app.services.suno_engine import build_suno_prompt_packs
from app.services.versioning import song_snapshot


DEFAULT_STRUCTURE = [
    ("Intro", 4, 2, "room tone, motif preview"),
    ("Verse", 8, 4, "tight vocal entry, low drums"),
    ("Pre-Chorus", 4, 5, "raise harmonic tension"),
    ("Chorus", 8, 7, "short hook, doubled vocal"),
    ("Post-Chorus", 4, 6, "chopped vocal or system response"),
    ("Verse", 8, 4, "second image set, add counter rhythm"),
    ("Pre-Chorus", 4, 6, "stronger lift"),
    ("Chorus", 8, 8, "fuller hook"),
    ("Bridge", 8, 5, "spoken-rap or stripped reflection"),
    ("Final Chorus", 8, 9, "final doubled hook"),
    ("Outro", 4, 2, "fade room tone and machine hum"),
]


def arrangement_rows() -> list[dict]:
    rows = []
    start = 1
    for section, bars, energy, notes in DEFAULT_STRUCTURE:
        end = start + bars - 1
        rows.append(
            {
                "section": section,
                "start_bar": start,
                "end_bar": end,
                "length_bars": bars,
                "energy_level": energy,
                "production_notes": notes,
            }
        )
        start = end + 1
    return rows


def _ticks_per_bar(mid: MidiFile) -> int:
    return mid.ticks_per_beat * 4


def build_skeleton_midi(song: Song, markers_only: bool = False) -> bytes:
    mid = MidiFile(ticks_per_beat=480)
    tempo_track = MidiTrack()
    mid.tracks.append(tempo_track)
    tempo_track.append(MetaMessage("track_name", name="STRUCTURE_MARKERS", time=0))
    tempo_track.append(MetaMessage("set_tempo", tempo=bpm2tempo(song.bpm or 92), time=0))

    current_tick = 0
    ticks_per_bar = _ticks_per_bar(mid)
    for row in arrangement_rows():
        tempo_track.append(MetaMessage("marker", text=row["section"], time=current_tick))
        current_tick = row["length_bars"] * ticks_per_bar
    tempo_track.append(MetaMessage("end_of_track", time=0))

    if not markers_only:
        tracks = [
            ("DRUMS_KICK", 36, 0, 4),
            ("DRUMS_SNARE", 38, 480, 4),
            ("BASS_GUIDE", 40, 0, 8),
            ("CHORDS_GUIDE", 60, 0, 16),
            ("MELODY_PLACEHOLDER", 72, 0, 8),
            ("VOCAL_GUIDE_PLACEHOLDER", 67, 240, 8),
        ]
        total_bars = sum(row["length_bars"] for row in arrangement_rows())
        for name, note, offset, every_beats in tracks:
            track = MidiTrack()
            mid.tracks.append(track)
            track.append(MetaMessage("track_name", name=name, time=0))
            absolute = offset
            last = 0
            step = mid.ticks_per_beat * every_beats
            while absolute < total_bars * ticks_per_bar:
                delta = max(0, absolute - last)
                track.append(Message("note_on", note=note, velocity=58, time=delta))
                track.append(Message("note_off", note=note, velocity=0, time=240))
                last = absolute + 240
                absolute += step
            track.append(MetaMessage("end_of_track", time=0))

    buffer = io.BytesIO()
    mid.save(file=buffer)
    return buffer.getvalue()


def build_arrangement_csv() -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["section", "start_bar", "end_bar", "length_bars", "energy_level", "production_notes"],
    )
    writer.writeheader()
    writer.writerows(arrangement_rows())
    return buffer.getvalue()


def build_musicxml_skeleton(song: Song) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <work><work-title>{song.title}</work-title></work>
  <part-list>
    <score-part id="P1"><part-name>Lead Vocal Guide</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <direction placement="above"><direction-type><words>Tempo {song.bpm or 92} BPM</words></direction-type></direction>
      <note><rest/><duration>4</duration><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""


def cubase_notes(song: Song) -> str:
    return f"""Cubase Import Notes for {song.title}

This pack intentionally does not include a native .cpr file. Cubase project files are not a stable public interchange format.

Suggested workflow:
1. Create a new Cubase project and set tempo to {song.bpm or 92} BPM.
2. Import skeleton.mid. It contains guide tracks for drums, bass, chords, melody, and vocal placeholders.
3. Import structure_markers.mid or use the marker events from skeleton.mid to create a marker track.
4. Import skeleton.musicxml if you want a notation placeholder.
5. Generate audio in Suno using suno_prompt.txt, then download stems/audio/MIDI where available.
6. Manually align Suno audio or MIDI to bar 1 and adjust section lengths against arrangement.csv.
"""


def _saved_prompt_pack(db: Session, song: Song) -> dict | None:
    if song.current_prompt_pack_id:
        artifact = db.get(CreativeArtifact, song.current_prompt_pack_id)
        if artifact and artifact.song_id == song.id and artifact.artifact_type == "suno_prompt_pack":
            return artifact.content or None
    artifact = db.scalar(
        select(CreativeArtifact)
        .where(CreativeArtifact.song_id == song.id)
        .where(CreativeArtifact.artifact_type == "suno_prompt_pack")
        .where(CreativeArtifact.status == "accepted")
        .order_by(CreativeArtifact.updated_at.desc())
        .limit(1)
    )
    return (artifact.content or None) if artifact else None


def create_cubase_pack(db: Session, song: Song) -> Path:
    prompt_data = _saved_prompt_pack(db, song) or build_suno_prompt_packs(song, db=db)
    suno = prompt_data["recommended_pack"]
    settings = suno.get("advanced_settings") or {}
    validation = suno.get("validation") or {}
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{song.id}_cubase_pack.zip")
    temp.close()
    path = Path(temp.name)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("song.json", json.dumps(song_snapshot(song), ensure_ascii=False, indent=2))
        zf.writestr(
            "suno_prompt.txt",
            (
                f"RECOMMENDED VARIANT\n{suno.get('variant')} / {suno.get('variant_role')}\n\n"
                f"STYLE PROMPT\n{suno.get('style_prompt')}\n\n"
                f"LYRICS PROMPT\n{suno.get('lyrics_prompt')}\n\n"
                f"EXCLUDE PROMPT\n{suno.get('exclude_prompt')}\n\n"
                "ADVANCED SETTINGS\n"
                f"Weirdness: {settings.get('weirdness')}\n"
                f"Style Influence: {settings.get('style_influence')}\n"
                f"Audio Influence: {settings.get('audio_influence')}\n\n"
                f"VALIDATION SUMMARY\nScore: {validation.get('score')}\n"
                f"Warnings: {', '.join(validation.get('warnings', []) or []) or 'none'}\n"
                f"Blocking Issues: {', '.join(validation.get('blocking_issues', []) or []) or 'none'}\n"
            ),
        )
        zf.writestr("lyrics.txt", song.lyrics or "")
        zf.writestr("arrangement.csv", build_arrangement_csv())
        zf.writestr("cubase_import_notes.txt", cubase_notes(song))
        zf.writestr("skeleton.mid", build_skeleton_midi(song, markers_only=False))
        zf.writestr("structure_markers.mid", build_skeleton_midi(song, markers_only=True))
        zf.writestr("skeleton.musicxml", build_musicxml_skeleton(song))

    return path
