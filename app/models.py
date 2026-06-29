from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
    current_stage: Mapped[str] = mapped_column(String(48), default="diagnosis", index=True)
    stage_status: Mapped[str] = mapped_column(String(48), default="not_started", index=True)
    locked_hook: Mapped[str] = mapped_column(Text, default="")
    current_structure_route: Mapped[str] = mapped_column(String(64), default="")
    current_prompt_pack_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    ep: Mapped[EPState] = relationship(back_populates="songs")
    sessions: Mapped[list["CreativeSession"]] = relationship(back_populates="song", cascade="all, delete-orphan")
    artifacts: Mapped[list["CreativeArtifact"]] = relationship(back_populates="song", cascade="all, delete-orphan")
    versions: Mapped[list["SongVersion"]] = relationship(
        back_populates="song", cascade="all, delete-orphan", order_by="SongVersion.version_number"
    )
    asset_files: Mapped[list["AssetFile"]] = relationship(back_populates="song", cascade="all, delete-orphan")


class CreativeSession(Base):
    __tablename__ = "creative_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(48), index=True)
    mode: Mapped[str] = mapped_column(String(48), default="strict")
    output_mode: Mapped[str] = mapped_column(String(48), default="stage_fit")
    user_goal: Mapped[str] = mapped_column(Text, default="")
    user_message: Mapped[str] = mapped_column(Text, default="")
    assistant_message: Mapped[str] = mapped_column(Text, default="")
    stage_recommendation: Mapped[dict] = mapped_column(JSON, default=dict)
    next_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(48), default="completed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    song: Mapped[Song] = relationship(back_populates="sessions")
    artifacts: Mapped[list["CreativeArtifact"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class CreativeArtifact(Base):
    __tablename__ = "creative_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("creative_sessions.id"), nullable=True, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(48), default="pending", index=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    song: Mapped[Song] = relationship(back_populates="artifacts")
    session: Mapped[CreativeSession | None] = relationship(back_populates="artifacts")
    asset_files: Mapped[list["AssetFile"]] = relationship(back_populates="artifact")


class SongVersion(Base):
    __tablename__ = "song_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("creative_sessions.id"), nullable=True, index=True)
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    version_label: Mapped[str] = mapped_column(String(255), default="")
    change_type: Mapped[str] = mapped_column(String(64), default="full")
    artifact_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    content_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    song: Mapped[Song] = relationship(back_populates="versions")
    session: Mapped[CreativeSession | None] = relationship()


class AssetFile(Base):
    __tablename__ = "asset_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("creative_sessions.id"), nullable=True, index=True)
    artifact_id: Mapped[int | None] = mapped_column(ForeignKey("creative_artifacts.id"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(64), default="")
    mime_type: Mapped[str] = mapped_column(String(128), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(64), default="other")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    song: Mapped[Song] = relationship(back_populates="asset_files")
    session: Mapped[CreativeSession | None] = relationship()
    artifact: Mapped[CreativeArtifact | None] = relationship(back_populates="asset_files")


class ImportedAsset(Base):
    __tablename__ = "imported_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(32))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
