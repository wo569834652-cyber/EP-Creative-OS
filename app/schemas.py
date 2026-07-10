from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


StageName = Literal[
    "diagnosis",
    "hook_lab",
    "structure_lab",
    "lyrics_draft",
    "suno_prompt_lab",
    "generation_review",
    "asset_organizer",
    "parked",
    "done",
]


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
    current_stage: str = "diagnosis"
    stage_status: str = "not_started"
    locked_hook: str = ""
    current_structure_route: str = ""
    current_prompt_pack_id: int | None = None


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


class StageInfo(BaseModel):
    key: str
    label: str
    description: str
    completion: list[str]


class SessionCreate(BaseModel):
    stage: str | None = None
    mode: Literal["strict", "producer", "free"] = "strict"
    output_mode: Literal["stage_fit", "deep_analysis", "cards_only"] = "stage_fit"
    user_goal: str = ""
    user_message: str = ""


class StageRecommendation(BaseModel):
    current_stage: str
    next_stage: str | None = None
    reason: str = ""
    requires_user_confirmation: bool = True


class CreativeArtifactRead(BaseModel):
    id: int
    song_id: int
    session_id: int | None
    artifact_type: str
    title: str
    summary: str
    content: dict[str, Any]
    status: str
    is_recommended: bool
    is_current: bool
    locked: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionRead(BaseModel):
    id: int
    song_id: int
    stage: str
    mode: str
    output_mode: str
    user_goal: str
    user_message: str
    assistant_message: str
    stage_recommendation: dict[str, Any]
    next_actions: list[str]
    status: str
    created_at: datetime
    artifacts: list[CreativeArtifactRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ArtifactActionResponse(BaseModel):
    artifact: CreativeArtifactRead
    version_id: int | None = None


class StageConfirmRequest(BaseModel):
    next_stage: str


class HookRequest(BaseModel):
    hook_goal: str
    style_reference: str | None = None
    language_mix: str | None = None
    count: int = Field(default=5, ge=1, le=5)


class HookOption(BaseModel):
    hook_text: str
    why_it_works: str
    rhythm_notes: str
    suno_risk: str
    score: int
    version_label: str = ""
    angle: str = ""
    innovation: int = 1
    use_case: str = ""


class HookResponse(BaseModel):
    hooks: list[HookOption]


class SunoPromptPackResponse(BaseModel):
    artifact: CreativeArtifactRead
    packs: list[dict[str, Any]]
    recommended_variant: str


class GenerationReviewCreate(BaseModel):
    take_name: str
    prompt_pack_artifact_id: int | None = None
    prompt_pack_variant: str | None = None
    text_feedback: str = ""
    hook_accuracy: int = Field(default=3, ge=1, le=5)
    style_accuracy: int = Field(default=3, ge=1, le=5)
    section_structure: int = Field(default=3, ge=1, le=5)
    diction_singability: int = Field(default=3, ge=1, le=5)
    emotional_fit: int = Field(default=3, ge=1, le=5)
    production_usability: int = Field(default=3, ge=1, le=5)


class VersionRead(BaseModel):
    id: int
    song_id: int
    session_id: int | None
    version_number: int
    version_label: str
    change_type: str
    artifact_ids: list[int]
    content_snapshot: dict[str, Any]
    summary: str
    change_summary: str
    locked: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiffResponse(BaseModel):
    from_version: int
    to_version: int
    diff: str


class AssetFileRead(BaseModel):
    id: int
    song_id: int
    session_id: int | None
    artifact_id: int | None
    filename: str
    stored_path: str
    file_type: str
    mime_type: str
    size_bytes: int
    sha256: str
    role: str
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    metadata: dict


class ChatRequest(BaseModel):
    ep_id: int
    song_id: int | None = None
    mode: Literal["ideation", "critique", "rewrite", "suno_prompt", "direction_fix", "hook_generation"]
    user_message: str


class ChatResponse(BaseModel):
    assistant_message: str
    suggested_actions: list[str] = Field(default_factory=list)
    extracted_updates: dict | None = None


class SunoResponse(BaseModel):
    title: str
    style_prompt: str
    lyrics_prompt: str
    negative_style_terms: list[str]
    bpm: int
    generation_notes: str
