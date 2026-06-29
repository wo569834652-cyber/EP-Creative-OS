# EP Creative OS V1 Implementation Plan

## Branch

Work happens on `v1-rebuild`.

## Implementation Goals

Refactor the V0 API checklist into a usable V1 creative production workspace.

The work is complete when the user can run the `访问失败` acceptance path from diagnosis to asset bundle export.

## Step 1: Data Model

Add or update:

- song stage fields
- `CreativeSession`
- `CreativeArtifact`
- `SongVersion` as creative checkpoint
- `AssetFile`

Keep startup seed behavior.

## Step 2: Services

Implement:

- stage definitions and display metadata
- session orchestration
- artifact lifecycle transitions
- version creation from accepted artifacts
- retention/pruning helper
- asset storage helper
- asset bundle exporter

## Step 3: AI Contract

Implement:

- stage-specific local fallback generation
- DeepSeek prompt assembly
- structured response parser where available
- deterministic artifact generation for core V1 stages

The app should remain useful without an API key, but with a key it should call `deepseek-v4-pro`.

## Step 4: Suno Prompt Engine

Implement deterministic prompt pack builder:

- max 3 variants
- exactly one recommended variant
- quality checks
- forbidden Style Prompt language labels
- revision strategy

## Step 5: APIs

Required V1 APIs:

- `GET /api/health`
- `GET /api/eps`
- `POST /api/eps`
- `GET /api/ep`
- `PUT /api/ep`
- `GET /api/songs`
- `GET /api/songs/{song_id}`
- `PUT /api/songs/{song_id}`
- `POST /api/songs/{song_id}/sessions`
- `GET /api/songs/{song_id}/sessions`
- `GET /api/songs/{song_id}/artifacts`
- `POST /api/artifacts/{artifact_id}/accept`
- `POST /api/artifacts/{artifact_id}/lock`
- `POST /api/artifacts/{artifact_id}/discard`
- `POST /api/artifacts/{artifact_id}/set-current`
- `POST /api/songs/{song_id}/stage/confirm`
- `POST /api/songs/{song_id}/suno-prompt-packs`
- `POST /api/songs/{song_id}/generation-reviews`
- `POST /api/songs/{song_id}/assets`
- `POST /api/songs/{song_id}/exports/asset-bundle`

V0 APIs can remain as compatibility wrappers if cheap.

## Step 6: Frontend

Rebuild `/` as Chinese V1 workspace:

- left song navigator
- center producer session
- right artifact/version board
- advanced song archive drawer
- generation review form
- asset upload and bundle export

## Step 7: Tests

API tests:

- health
- seed includes `访问失败`
- session creates pending artifacts
- artifact accept/lock/discard
- stage confirm
- Suno prompt packs max 3 with one recommendation
- generation review save
- asset upload metadata
- asset bundle zip contents

Frontend manual checks:

- Chinese labels render correctly
- choose `访问失败`
- run stage
- accept artifact
- generate prompt pack
- log generation review
- upload asset
- export bundle

## Non-Goals

- multi-user accounts
- cloud deployment
- real audio analysis
- native Cubase `.cpr`
- complex MIDI arrangement pack
- multiple EP workspaces

## Done Criteria

- `pytest -q` passes.
- Local server starts.
- `/` opens V1 Chinese workspace.
- Main acceptance path for `访问失败` works.
- `.env` remains ignored.
- Branch `v1-rebuild` is pushed to GitHub.
