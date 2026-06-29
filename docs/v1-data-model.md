# EP Creative OS V1 Data Model

## Principles

SQLite should store structured metadata and searchable creative text. Large files and generated bundles belong on disk.

Do not store ZIP, audio, uploaded MIDI, or exported bundle bytes in SQLite.

Default retention:

- Keep recent automatic sessions per song: 30.
- Keep locked artifacts and locked versions permanently.
- Keep asset file records permanently while the physical file exists.

## Tables

## `ep_states`

Existing EP state table remains. It stores one local EP project. V1 can store multiple EP projects and the frontend selects one active project at a time.

Important fields:

- `title`
- `one_liner`
- `core_theme`
- `world_view`
- `emotional_keywords`
- `aesthetic_keywords`
- `sonic_layers`
- `narrative_arc`
- `song_list`

## `songs`

Existing song table is extended.

Fields:

- `id`
- `ep_id`
- `title`
- `function_in_ep`
- `concept`
- `emotional_goal`
- `bpm`
- `genre_direction`
- `language_plan`
- `lyrics`
- `style_prompt`
- `lyrics_prompt`
- `notes`
- `current_stage`
- `stage_status`
- `locked_hook`
- `current_structure_route`
- `current_prompt_pack_id`
- `created_at`
- `updated_at`

Allowed `current_stage` values:

- `diagnosis`
- `hook_lab`
- `structure_lab`
- `lyrics_draft`
- `suno_prompt_lab`
- `generation_review`
- `asset_organizer`
- `parked`
- `done`

Allowed `stage_status` values:

- `not_started`
- `in_progress`
- `ready_to_advance`
- `confirmed`

## `creative_sessions`

A creative session is one AI-assisted production turn or stage run.

Fields:

- `id`
- `song_id`
- `stage`
- `mode`
- `output_mode`
- `user_goal`
- `user_message`
- `assistant_message`
- `stage_recommendation`
- `next_actions`
- `status`
- `created_at`

Allowed `status` values:

- `draft`
- `completed`
- `archived`

Retention:

- Auto-prune unlocked old sessions beyond 30 per song.
- Sessions with locked artifacts are retained.

## `creative_artifacts`

Artifacts are the durable creative cards produced by sessions.

Fields:

- `id`
- `song_id`
- `session_id`
- `artifact_type`
- `title`
- `summary`
- `content`
- `status`
- `is_recommended`
- `is_current`
- `locked`
- `created_at`
- `updated_at`

Allowed `artifact_type` values:

- `diagnosis`
- `hook_set`
- `structure_route`
- `lyrics_draft`
- `suno_prompt_pack`
- `generation_review`
- `asset_bundle`

Allowed `status` values:

- `pending`
- `accepted`
- `discarded`

Retention:

- Pending artifacts can be pruned with old sessions.
- Accepted artifacts are retained while their session is retained.
- Locked artifacts are retained permanently.

Size control:

- Each artifact content should stay below 50 KB.
- Long uploaded file contents are never stored here.
- Large exports store file paths in `asset_files`.

## `song_versions`

Versions are creative decision checkpoints, not mechanical full-row snapshots.

Fields:

- `id`
- `song_id`
- `session_id`
- `version_number`
- `version_label`
- `change_type`
- `artifact_ids`
- `summary`
- `locked`
- `created_at`

Allowed `change_type` values:

- `diagnosis`
- `hook`
- `structure`
- `lyrics`
- `suno_prompt`
- `generation_review`
- `asset_bundle`
- `full`

Retention:

- Keep recent 30 unlocked versions per song.
- Keep locked versions permanently.

## `asset_files`

Asset files index disk files.

Fields:

- `id`
- `song_id`
- `session_id`
- `artifact_id`
- `filename`
- `stored_path`
- `file_type`
- `mime_type`
- `size_bytes`
- `sha256`
- `role`
- `metadata_json`
- `created_at`

Allowed roles:

- `suno_audio`
- `suno_midi`
- `stem`
- `reference`
- `export_bundle`
- `notes`
- `other`

Storage paths:

- Imports: `storage/imports/{song_id}/{asset_id}_{safe_filename}`
- Exports: `storage/exports/{song_id}/{timestamp}_asset_bundle.zip`

## Migration Strategy

V1 can recreate tables locally during development. Because V0 is a prototype, no Alembic migration is required yet.

Startup should:

- Create missing tables.
- Seed the EP if empty.
- Ensure seeded songs have current stages.

For existing V0 databases, if columns are missing, V1 can either:

- start from a fresh local DB, or
- add missing columns using lightweight SQLite checks.

For this repo V1 implementation, tests use a temporary SQLite DB.

## Database Size Controls

- Do not store binary file content in DB.
- Store only artifact text and metadata.
- Limit artifact content to 50 KB.
- Limit automatic sessions per song to 30 unlocked sessions.
- Allow user-locked milestones to override pruning.
- Save bundle exports to disk and index them through `asset_files`.
