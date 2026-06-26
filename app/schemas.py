from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EPStateBase(BaseModel):
    title: str = ""
    one_liner: str = ""
    core_theme: str = ""
    world_view: str = ""
    emotional_keywords: list[str] = Field(default_factory=list)
    aesthetic_keywords: list[str] = Field(default_factory=list)
    sonic_layers: dict = Field(default_factory=dict)
    narrative_arc: str = ""
    song_list: list[str] = Field(default_factory=list)


class EPStateRead(EPStateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SongBase(BaseModel):
    title: str = ""
    function_in_ep: str = ""
    concept: str = ""
    emotional_goal: str = ""
    bpm: int = 92
    genre_direction: str = ""
    language_plan: str = ""
    lyrics: str = ""
    style_prompt: str = ""
    lyrics_prompt: str = ""
    notes: str = ""


class SongCreate(SongBase):
    ep_id: int | None = None


class SongUpdate(SongBase):
    change_summary: str | None = None


class SongRead(SongBase):
    id: int
    ep_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    ep_id: int
    song_id: int | None = None
    mode: Literal["ideation", "critique", "rewrite", "suno_prompt", "direction_fix", "hook_generation"]
    user_message: str


class ChatResponse(BaseModel):
    assistant_message: str
    suggested_actions: list[str] = Field(default_factory=list)
    extracted_updates: dict | None = None


class HookRequest(BaseModel):
    hook_goal: str
    style_reference: str | None = None
    language_mix: str | None = None
    count: int = Field(default=6, ge=1, le=12)


class HookOption(BaseModel):
    hook_text: str
    why_it_works: str
    rhythm_notes: str
    suno_risk: str
    score: int


class HookResponse(BaseModel):
    hooks: list[HookOption]


class SunoResponse(BaseModel):
    title: str
    style_prompt: str
    lyrics_prompt: str
    negative_style_terms: list[str]
    bpm: int
    generation_notes: str


class VersionRead(BaseModel):
    id: int
    song_id: int
    version_number: int
    change_type: str
    content_snapshot: dict
    change_summary: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiffResponse(BaseModel):
    from_version: int
    to_version: int
    diff: str


class ImportResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    metadata: dict
