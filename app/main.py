from contextlib import asynccontextmanager
import json

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.llm.deepseek_client import DeepSeekClient
from app.models import EPState, Song, SongVersion
from app.prompts.critique_prompt import CRITIQUE_PROMPT
from app.prompts.hook_prompt import HOOK_PROMPT
from app.prompts.producer_system_prompt import PRODUCER_SYSTEM_PROMPT
from app.prompts.rewrite_prompt import REWRITE_PROMPT
from app.prompts.suno_prompt import SUNO_PROMPT
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DiffResponse,
    EPStateBase,
    EPStateRead,
    HookRequest,
    HookResponse,
    ImportResponse,
    SongCreate,
    SongRead,
    SongUpdate,
    SunoResponse,
    VersionRead,
)
from app.seed import seed_database
from app.services.cubase_export import create_cubase_pack
from app.services.hooks import generate_hooks
from app.services.importer import import_suno_file
from app.services.suno import generate_suno_prompt
from app.services.versioning import create_version, detect_change_type, snapshot_diff, song_snapshot


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="EP Creative OS", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def get_ep_or_404(db: Session) -> EPState:
    ep = db.scalar(select(EPState).order_by(EPState.id).limit(1))
    if not ep:
        raise HTTPException(status_code=404, detail="EP state not found")
    return ep


def get_song_or_404(db: Session, song_id: int) -> Song:
    song = db.get(Song, song_id)
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/ep", response_model=EPStateRead)
def read_ep(db: Session = Depends(get_db)) -> EPState:
    return get_ep_or_404(db)


@app.put("/api/ep", response_model=EPStateRead)
def update_ep(payload: EPStateBase, db: Session = Depends(get_db)) -> EPState:
    ep = get_ep_or_404(db)
    for field, value in payload.model_dump().items():
        setattr(ep, field, value)
    db.commit()
    db.refresh(ep)
    return ep


@app.get("/api/songs", response_model=list[SongRead])
def list_songs(db: Session = Depends(get_db)) -> list[Song]:
    return list(db.scalars(select(Song).order_by(Song.id)).all())


@app.post("/api/songs", response_model=SongRead)
def create_song(payload: SongCreate, db: Session = Depends(get_db)) -> Song:
    ep_id = payload.ep_id or get_ep_or_404(db).id
    data = payload.model_dump(exclude={"ep_id"})
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


def mode_prompt(mode: str) -> str:
    return {
        "critique": CRITIQUE_PROMPT,
        "rewrite": REWRITE_PROMPT,
        "suno_prompt": SUNO_PROMPT,
        "hook_generation": HOOK_PROMPT,
    }.get(mode, "围绕 EP 概念进行创作发散，输出具体可执行建议。")


@app.post("/api/chat", response_model=ChatResponse)
async def creative_chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    ep = db.get(EPState, payload.ep_id)
    if not ep:
        raise HTTPException(status_code=404, detail="EP not found")
    song = db.get(Song, payload.song_id) if payload.song_id else None

    context = {
        "ep": {
            "title": ep.title,
            "one_liner": ep.one_liner,
            "core_theme": ep.core_theme,
            "sonic_layers": ep.sonic_layers,
            "narrative_arc": ep.narrative_arc,
            "song_list": ep.song_list,
        },
        "song": song_snapshot(song) if song else None,
        "mode": payload.mode,
    }
    messages = [
        {"role": "system", "content": PRODUCER_SYSTEM_PROMPT},
        {"role": "system", "content": mode_prompt(payload.mode)},
        {"role": "user", "content": f"Context JSON:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\nUser:\n{payload.user_message}"},
    ]
    ok, content = await DeepSeekClient().chat(messages)
    if not ok:
        return ChatResponse(
            assistant_message=content,
            suggested_actions=["在 .env 中配置 DEEPSEEK_API_KEY", "继续使用本地 Hook / Suno / Cubase 导出功能"],
            extracted_updates={"llm_available": False},
        )
    return ChatResponse(
        assistant_message=content,
        suggested_actions=["提取可执行修改点", "需要时把歌词或 prompt 保存为新版本"],
        extracted_updates={"llm_available": True},
    )


@app.post("/api/songs/{song_id}/hooks", response_model=HookResponse)
def hooks(song_id: int, payload: HookRequest, db: Session = Depends(get_db)) -> HookResponse:
    song = get_song_or_404(db, song_id)
    options = generate_hooks(song, payload.hook_goal, payload.style_reference, payload.language_mix, payload.count)
    song.notes = (song.notes or "") + "\n\nHook Engine:\n" + "\n".join(f"- {item.hook_text} ({item.score})" for item in options)
    create_version(db, song, "hook", f"Generated {len(options)} hook options")
    db.commit()
    return HookResponse(hooks=options)


@app.post("/api/songs/{song_id}/suno", response_model=SunoResponse)
def suno(song_id: int, db: Session = Depends(get_db)) -> SunoResponse:
    song = get_song_or_404(db, song_id)
    response = generate_suno_prompt(song)
    song.style_prompt = response.style_prompt
    song.lyrics_prompt = response.lyrics_prompt
    create_version(db, song, "style", "Generated Suno style and lyrics prompts")
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
