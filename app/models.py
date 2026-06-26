from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EPState(Base):
    __tablename__ = "ep_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    one_liner: Mapped[str] = mapped_column(Text, default="")
    core_theme: Mapped[str] = mapped_column(Text, default="")
    world_view: Mapped[str] = mapped_column(Text, default="")
    emotional_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    aesthetic_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    sonic_layers: Mapped[dict] = mapped_column(JSON, default=dict)
    narrative_arc: Mapped[str] = mapped_column(Text, default="")
    song_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    songs: Mapped[list["Song"]] = relationship(back_populates="ep", cascade="all, delete-orphan")


class Song(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ep_id: Mapped[int] = mapped_column(ForeignKey("ep_states.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    function_in_ep: Mapped[str] = mapped_column(Text, default="")
    concept: Mapped[str] = mapped_column(Text, default="")
    emotional_goal: Mapped[str] = mapped_column(Text, default="")
    bpm: Mapped[int] = mapped_column(Integer, default=92)
    genre_direction: Mapped[str] = mapped_column(Text, default="")
    language_plan: Mapped[str] = mapped_column(Text, default="")
    lyrics: Mapped[str] = mapped_column(Text, default="")
    style_prompt: Mapped[str] = mapped_column(Text, default="")
    lyrics_prompt: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    ep: Mapped[EPState] = relationship(back_populates="songs")
    versions: Mapped[list["SongVersion"]] = relationship(
        back_populates="song", cascade="all, delete-orphan", order_by="SongVersion.version_number"
    )


class SongVersion(Base):
    __tablename__ = "song_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    change_type: Mapped[str] = mapped_column(String(32), default="full")
    content_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    song: Mapped[Song] = relationship(back_populates="versions")


class ImportedAsset(Base):
    __tablename__ = "imported_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(32))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
