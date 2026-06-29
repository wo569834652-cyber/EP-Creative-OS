from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import Base, SessionLocal, engine, get_db
from app.llm.deepseek_client import DeepSeekClient
from app.models import AssetFile, CreativeArtifact, CreativeSession, EPState, Song, SongVersion
from app.prompts.producer_system_prompt import PRODUCER_SYSTEM_PROMPT
from app.schemas import (
    ArtifactActionResponse,
    AssetFileRead,
    ChatRequest,
    ChatResponse,
    CreativeArtifactRead,
    DiffResponse,
    EPStateBase,
    EPStateRead,
    GenerationReviewCreate,
    HookRequest,
    HookResponse,
    ImportResponse,
    SessionCreate,
    SessionRead,
    SongCreate,
    SongRead,
    SongUpdate,
    StageConfirmRequest,
    StageInfo,
    SunoPromptPackResponse,
    SunoResponse,
    VersionRead,
)
from app.seed import seed_database
from app.services.assets import create_asset_bundle, store_upload
from app.services.cubase_export import create_cubase_pack
from app.services.hooks import generate_hooks
from app.services.importer import import_suno_file
from app.services.session_engine import build_generation_review_with_ai, create_session_with_artifacts
from app.services.stages import STAGE_LABELS, next_stage, stage_metadata
from app.services.suno import generate_suno_prompt
from app.services.suno_engine import build_suno_prompt_packs
from app.services.versioning import create_version, create_version_from_artifact, detect_change_type, snapshot_diff, song_snapshot


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="EP Creative OS", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def get_ep_or_404(db: Session, ep_id: int | None = None) -> EPState:
    if ep_id is not None:
        ep = db.get(EPState, ep_id)
    else:
        ep = db.scalar(select(EPState).order_by(EPState.id).limit(1))
    if not ep:
        raise HTTPException(status_code=404, detail="EP state not found")
    return ep


def get_song_or_404(db: Session, song_id: int) -> Song:
    song = db.get(Song, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


def get_artifact_or_404(db: Session, artifact_id: int) -> CreativeArtifact:
    artifact = db.get(CreativeArtifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/stages", response_model=list[StageInfo])
def stages() -> list[dict]:
    return stage_metadata()


@app.get("/api/ep", response_model=EPStateRead)
def read_ep(ep_id: int | None = None, db: Session = Depends(get_db)) -> EPState:
    return get_ep_or_404(db, ep_id)


@app.put("/api/ep", response_model=EPStateRead)
def update_ep(payload: EPStateBase, ep_id: int | None = None, db: Session = Depends(get_db)) -> EPState:
    ep = get_ep_or_404(db, ep_id)
    for field, value in payload.model_dump().items():
        setattr(ep, field, value)
    db.commit()
    db.refresh(ep)
    return ep


@app.get("/api/eps", response_model=list[EPStateRead])
def list_eps(db: Session = Depends(get_db)) -> list[EPState]:
    return list(db.scalars(select(EPState).order_by(EPState.id)).all())


@app.post("/api/eps", response_model=EPStateRead)
def create_ep(payload: EPStateBase, db: Session = Depends(get_db)) -> EPState:
    ep = EPState(**payload.model_dump())
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@app.get("/api/songs", response_model=list[SongRead])
def list_songs(ep_id: int | None = None, db: Session = Depends(get_db)) -> list[Song]:
    query = select(Song).order_by(Song.id)
    if ep_id is not None:
        query = query.where(Song.ep_id == ep_id)
    return list(db.scalars(query).all())


@app.post("/api/songs", response_model=SongRead)
def create_song(payload: SongCreate, db: Session = Depends(get_db)) -> Song:
    ep_id = payload.ep_id or get_ep_or_404(db).id
    data = payload.model_dump(exclude={"ep_id", "change_summary"})
    song = Song(ep_id=ep_id, **data)
    db.add(song)
    db.flush()
    create_version(db, song, "full", "Initial song draft")
    db.commit()
    db.refresh(song)
    return song


@app.get("/api/songs/{song_id}", response_model=SongRead)
def read_song(song_id: int, db: Session = Depends(get_db)) -> Song:
    return get_song_or_404(db, song_id)


@app.put("/api/songs/{song_id}", response_model=SongRead)
def update_song(song_id: int, payload: SongUpdate, db: Session = Depends(get_db)) -> Song:
    song = get_song_or_404(db, song_id)
    before = song_snapshot(song)
    data = payload.model_dump(exclude={"change_summary"})
    for field, value in data.items():
        setattr(song, field, value)
    after = song_snapshot(song)
    if before != after:
        change_type = detect_change_type(before, after)
        create_version(db, song, change_type, payload.change_summary or f"Updated {change_type}")
    db.commit()
    db.refresh(song)
    return song


@app.delete("/api/songs/{song_id}")
def delete_song(song_id: int, db: Session = Depends(get_db)) -> dict:
    song = get_song_or_404(db, song_id)
    db.delete(song)
    db.commit()
    return {"deleted": True}


@app.post("/api/songs/{song_id}/sessions", response_model=SessionRead)
async def create_session(song_id: int, payload: SessionCreate, db: Session = Depends(get_db)) -> CreativeSession:
    song = get_song_or_404(db, song_id)
    ep = get_ep_or_404(db, song.ep_id)
    stage = payload.stage or song.current_stage
    session = await create_session_with_artifacts(
        db,
        song,
        ep,
        stage,
        payload.mode,
        payload.output_mode,
        payload.user_goal,
        payload.user_message,
    )
    db.commit()
    return db.scalar(
        select(CreativeSession)
        .where(CreativeSession.id == session.id)
        .options(selectinload(CreativeSession.artifacts))
    )


@app.get("/api/songs/{song_id}/sessions", response_model=list[SessionRead])
def list_sessions(song_id: int, db: Session = Depends(get_db)) -> list[CreativeSession]:
    get_song_or_404(db, song_id)
    return list(
        db.scalars(
            select(CreativeSession)
            .where(CreativeSession.song_id == song_id)
            .options(selectinload(CreativeSession.artifacts))
            .order_by(CreativeSession.created_at.desc())
        ).all()
    )


@app.get("/api/songs/{song_id}/artifacts", response_model=list[CreativeArtifactRead])
def list_artifacts(song_id: int, db: Session = Depends(get_db)) -> list[CreativeArtifact]:
    get_song_or_404(db, song_id)
    return list(
        db.scalars(
            select(CreativeArtifact)
            .where(CreativeArtifact.song_id == song_id)
            .order_by(CreativeArtifact.locked.desc(), CreativeArtifact.updated_at.desc())
        ).all()
    )


@app.post("/api/artifacts/{artifact_id}/accept", response_model=ArtifactActionResponse)
def accept_artifact(artifact_id: int, db: Session = Depends(get_db)) -> ArtifactActionResponse:
    artifact = get_artifact_or_404(db, artifact_id)
    artifact.status = "accepted"
    version = create_version_from_artifact(db, artifact)
    db.commit()
    db.refresh(artifact)
    return ArtifactActionResponse(artifact=artifact, version_id=version.id)


@app.post("/api/artifacts/{artifact_id}/lock", response_model=ArtifactActionResponse)
def lock_artifact(artifact_id: int, db: Session = Depends(get_db)) -> ArtifactActionResponse:
    artifact = get_artifact_or_404(db, artifact_id)
    artifact.status = "accepted"
    artifact.locked = True
    version = create_version_from_artifact(db, artifact)
    version.locked = True
    db.commit()
    db.refresh(artifact)
    return ArtifactActionResponse(artifact=artifact, version_id=version.id)


@app.post("/api/artifacts/{artifact_id}/discard", response_model=ArtifactActionResponse)
def discard_artifact(artifact_id: int, db: Session = Depends(get_db)) -> ArtifactActionResponse:
    artifact = get_artifact_or_404(db, artifact_id)
    artifact.status = "discarded"
    artifact.is_current = False
    db.commit()
    db.refresh(artifact)
    return ArtifactActionResponse(artifact=artifact, version_id=None)


@app.post("/api/artifacts/{artifact_id}/set-current", response_model=ArtifactActionResponse)
def set_current_artifact(artifact_id: int, db: Session = Depends(get_db)) -> ArtifactActionResponse:
    artifact = get_artifact_or_404(db, artifact_id)
    peers = db.scalars(
        select(CreativeArtifact)
        .where(CreativeArtifact.song_id == artifact.song_id)
        .where(CreativeArtifact.artifact_type == artifact.artifact_type)
    ).all()
    for peer in peers:
        peer.is_current = False
    artifact.is_current = True
    if artifact.status == "pending":
        artifact.status = "accepted"
    version = create_version_from_artifact(db, artifact)
    db.commit()
    db.refresh(artifact)
    return ArtifactActionResponse(artifact=artifact, version_id=version.id)


@app.post("/api/songs/{song_id}/stage/confirm", response_model=SongRead)
def confirm_stage(song_id: int, payload: StageConfirmRequest, db: Session = Depends(get_db)) -> Song:
    song = get_song_or_404(db, song_id)
    pending_count = db.scalar(
        select(CreativeArtifact)
        .where(CreativeArtifact.song_id == song.id)
        .where(CreativeArtifact.status == "pending")
        .limit(1)
    )
    if pending_count:
        raise HTTPException(status_code=409, detail="还有待确认创作产物。请先保存、不采用或设为当前，再进入下一阶段。")
    song.current_stage = payload.next_stage
    song.stage_status = "confirmed"
    create_version(db, song, "full", f"进入阶段：{STAGE_LABELS.get(payload.next_stage, payload.next_stage)}")
    db.commit()
    db.refresh(song)
    return song


@app.post("/api/songs/{song_id}/suno-prompt-packs", response_model=SunoPromptPackResponse)
def create_suno_prompt_packs(song_id: int, db: Session = Depends(get_db)) -> SunoPromptPackResponse:
    song = get_song_or_404(db, song_id)
    content = build_suno_prompt_packs(song)
    artifact = CreativeArtifact(
        song_id=song.id,
        artifact_type="suno_prompt_pack",
        title=f"{song.title} / Suno Prompt 包",
        summary=f"推荐方案：{content['recommended_variant']}",
        content=content,
        is_recommended=True,
    )
    db.add(artifact)
    song.stage_status = "ready_to_advance"
    db.commit()
    db.refresh(artifact)
    return SunoPromptPackResponse(
        artifact=artifact,
        packs=content["packs"],
        recommended_variant=content["recommended_variant"],
    )


@app.post("/api/songs/{song_id}/generation-reviews", response_model=CreativeArtifactRead)
async def create_generation_review(song_id: int, payload: GenerationReviewCreate, db: Session = Depends(get_db)) -> CreativeArtifact:
    song = get_song_or_404(db, song_id)
    ep = get_ep_or_404(db, song.ep_id)
    scores = {
        "hook_accuracy": payload.hook_accuracy,
        "style_accuracy": payload.style_accuracy,
        "section_structure": payload.section_structure,
        "diction_singability": payload.diction_singability,
        "emotional_fit": payload.emotional_fit,
        "production_usability": payload.production_usability,
    }
    feedback_context = {
        "take_name": payload.take_name,
        "prompt_pack_artifact_id": payload.prompt_pack_artifact_id,
        "text_feedback": payload.text_feedback,
        "scores": scores,
    }
    ai_payload = await build_generation_review_with_ai(song, ep, feedback_context)
    if ai_payload:
        content = {
            **ai_payload["content"],
            "take_name": payload.take_name,
            "prompt_pack_artifact_id": payload.prompt_pack_artifact_id,
            "text_feedback": payload.text_feedback,
            "scores": scores,
        }
        artifact = CreativeArtifact(
            song_id=song.id,
            artifact_type="generation_review",
            title=f"{song.title} / AI 生成复盘 / {payload.take_name}",
            summary=ai_payload["summary"],
            content=content,
            status="accepted",
            is_recommended=True,
        )
        db.add(artifact)
        db.flush()
        create_version(db, song, "generation_review", f"AI 记录生成复盘：{payload.take_name}", artifact_ids=[artifact.id])
        db.commit()
        db.refresh(artifact)
        return artifact

    lowest = min(scores, key=scores.get)
    revision_map = {
        "hook_accuracy": "优先缩短 Hook，并在 Lyrics Prompt 中重复标注副歌第一句。",
        "style_accuracy": "优先修改 Style Prompt 的 groove、drums、instrument palette。",
        "section_structure": "减少段落标签数量，明确 Chorus 和 Bridge 的功能。",
        "diction_singability": "缩短中文长句，增加停顿和半唱提示。",
        "emotional_fit": "调整 vocal direction 和 mood，不要先改曲式。",
        "production_usability": "降低编曲复杂度，保留更干的主唱和更清楚的节拍。",
    }
    content = {
        "take_name": payload.take_name,
        "prompt_pack_artifact_id": payload.prompt_pack_artifact_id,
        "text_feedback": payload.text_feedback,
        "scores": scores,
        "next_revision_target": lowest,
        "next_revision_advice": revision_map[lowest],
        "source": "local_fallback",
        "fallback": True,
    }
    artifact = CreativeArtifact(
        song_id=song.id,
        artifact_type="generation_review",
        title=f"{song.title} / 生成复盘 / {payload.take_name}",
        summary=revision_map[lowest],
        content=content,
        status="accepted",
        is_recommended=True,
    )
    db.add(artifact)
    db.flush()
    create_version(db, song, "generation_review", f"记录生成复盘：{payload.take_name}", artifact_ids=[artifact.id])
    db.commit()
    db.refresh(artifact)
    return artifact


@app.post("/api/songs/{song_id}/assets", response_model=AssetFileRead)
async def upload_song_asset(
    song_id: int,
    role: str = Form("other"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AssetFile:
    song = get_song_or_404(db, song_id)
    return await store_upload(db, song, file, role)


@app.get("/api/songs/{song_id}/assets", response_model=list[AssetFileRead])
def list_song_assets(song_id: int, db: Session = Depends(get_db)) -> list[AssetFile]:
    get_song_or_404(db, song_id)
    return list(db.scalars(select(AssetFile).where(AssetFile.song_id == song_id).order_by(AssetFile.created_at.desc())).all())


@app.post("/api/songs/{song_id}/exports/asset-bundle")
def export_asset_bundle(song_id: int, db: Session = Depends(get_db)) -> FileResponse:
    song = get_song_or_404(db, song_id)
    path = create_asset_bundle(db, song)
    filename = f"{song.title or 'song'}_asset_bundle.zip".replace("/", "_").replace("\\", "_")
    return FileResponse(path, filename=filename, media_type="application/zip")


@app.post("/api/chat", response_model=ChatResponse)
async def creative_chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    ep = db.get(EPState, payload.ep_id)
    if not ep:
        raise HTTPException(status_code=404, detail="EP not found")
    song = db.get(Song, payload.song_id) if payload.song_id else None
    context = {
        "ep_title": ep.title,
        "song": song_snapshot(song) if song else None,
        "mode": payload.mode,
    }
    messages = [
        {"role": "system", "content": PRODUCER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Context: {context}\n\nUser: {payload.user_message}"},
    ]
    ok, content = await DeepSeekClient().chat(messages)
    if not ok:
        return ChatResponse(
            assistant_message=content,
            suggested_actions=["配置 DEEPSEEK_API_KEY", "继续使用本地 V1 阶段工作流"],
            extracted_updates={"llm_available": False},
        )
    return ChatResponse(
        assistant_message=content,
        suggested_actions=["把有用结论保存为 Artifact", "需要时推进当前阶段"],
        extracted_updates={"llm_available": True},
    )


@app.post("/api/songs/{song_id}/hooks", response_model=HookResponse)
def hooks(song_id: int, payload: HookRequest, db: Session = Depends(get_db)) -> HookResponse:
    song = get_song_or_404(db, song_id)
    options = generate_hooks(song, payload.hook_goal, payload.style_reference, payload.language_mix, payload.count)
    return HookResponse(hooks=options)


@app.post("/api/songs/{song_id}/suno", response_model=SunoResponse)
def suno(song_id: int, db: Session = Depends(get_db)) -> SunoResponse:
    song = get_song_or_404(db, song_id)
    response = generate_suno_prompt(song)
    song.style_prompt = response.style_prompt
    song.lyrics_prompt = response.lyrics_prompt
    create_version(db, song, "suno_prompt", "Generated V1 Suno prompt")
    db.commit()
    return response


@app.get("/api/songs/{song_id}/versions", response_model=list[VersionRead])
def list_versions(song_id: int, db: Session = Depends(get_db)) -> list[SongVersion]:
    get_song_or_404(db, song_id)
    return list(
        db.scalars(
            select(SongVersion).where(SongVersion.song_id == song_id).order_by(SongVersion.version_number.desc())
        ).all()
    )


@app.get("/api/songs/{song_id}/versions/{version_id}", response_model=VersionRead)
def read_version(song_id: int, version_id: int, db: Session = Depends(get_db)) -> SongVersion:
    version = db.get(SongVersion, version_id)
    if not version or version.song_id != song_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@app.get("/api/songs/{song_id}/diff", response_model=DiffResponse)
def diff_versions(song_id: int, from_version: int, to_version: int, db: Session = Depends(get_db)) -> DiffResponse:
    get_song_or_404(db, song_id)
    left = db.get(SongVersion, from_version)
    right = db.get(SongVersion, to_version)
    if not left or not right or left.song_id != song_id or right.song_id != song_id:
        raise HTTPException(status_code=404, detail="Version not found for this song")
    return DiffResponse(from_version=from_version, to_version=to_version, diff=snapshot_diff(left, right))


@app.post("/api/songs/{song_id}/exports/cubase-pack")
def export_cubase_pack(song_id: int, db: Session = Depends(get_db)) -> FileResponse:
    song = get_song_or_404(db, song_id)
    path = create_cubase_pack(song)
    filename = f"{song.title or 'song'}_cubase_pack.zip".replace("/", "_").replace("\\", "_")
    return FileResponse(path, filename=filename, media_type="application/zip")


@app.post("/api/import/suno-midi", response_model=ImportResponse)
async def import_suno_midi(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportResponse:
    try:
        asset = await import_suno_file(db, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportResponse(
        id=asset.id,
        filename=asset.filename,
        file_type=asset.file_type,
        metadata=asset.metadata_json,
    )
