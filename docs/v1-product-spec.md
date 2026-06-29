# EP Creative OS V1 Product Spec

## Product Goal

EP Creative OS V1 is a local creative production workspace for moving one concept EP from scattered ideas into usable Suno prompts, reviewable generations, and organized production assets.

The product is not a generic chat app, not a backend API checklist, and not a fake Cubase project generator. Its job is to help the user make creative decisions and preserve them as reusable artifacts.

## V1 Boundary

V1 supports multiple local EP projects in SQLite, with one active project selected in the workspace. It does not support multi-user accounts, cloud sync, team-level project management, real audio analysis, or native Cubase `.cpr` generation.

V1 must support the full path:

1. Song stage status
2. Producer session
3. Structured artifact cards
4. User confirmation
5. Version board
6. Suno Prompt Pack
7. Generation Review Log
8. Asset Organizer

## Primary Acceptance Song

The main V1 acceptance path is the song `访问失败`.

This song must prove the product can handle:

- EP narrative function: old conversations, old relationships, and old selves cannot be reopened.
- Hook references: `access denied`, `never try again`, `可我停在你之外`, `访问失败`.
- Structure route: Error-System Route by default.
- Optional structure innovation when needed.
- Suno prompt quality without language-label pollution in Style Prompt.
- Generation review based on user feedback and uploaded assets.
- Final asset bundle export for production organization.

## Core Workflow

The default V1 workflow is a strict producer pipeline. Each stage generates structured artifacts and recommends next actions. The AI can recommend stage advancement, but the user confirms it.

Stages:

1. `diagnosis`
   - Identify the song's EP function.
   - Identify the biggest current creative blocker.
   - Recommend the next stage.

2. `hook_lab`
   - Generate 3 to 5 hook options.
   - Score each hook for singability, repetition, vowel/rhyme unity, concept density, and Suno risk.
   - Recommend one hook.

3. `structure_lab`
   - Recommend a structure route, not a fixed pop template.
   - Default to Suno-executable stability.
   - Provide optional innovation when the song needs it.

4. `lyrics_draft`
   - Generate or revise lyric material based on the selected hook and structure route.
   - Keep chorus lines short and singable.
   - Put complex concepts into verse, bridge, or spoken/half-sung sections.

5. `suno_prompt_lab`
   - Generate up to three Suno Prompt Pack options: `primary`, `alternate`, `experimental`.
   - Recommend exactly one.
   - Include quality checks, revision strategy, and Suno risks.

6. `generation_review`
   - Let the user log Suno results with text feedback, scores, and uploaded files.
   - Do not pretend to analyze audio content.
   - Generate next-round revision guidance.

7. `asset_organizer`
   - Organize current lyrics, prompts, reviews, notes, and uploaded files.
   - Export a production asset bundle.
   - Provide Cubase import notes only as organization guidance.

Additional states:

- `parked`: paused without deletion.
- `done`: current song has reached the user's current production target.

## Structure Lab Routes

V1 uses structure strategies instead of one fixed song form.

- `classic_pop`: stable Intro / Verse / Pre / Chorus / Bridge style for reliable generation.
- `loop_mantra`: repeated short phrase with gradual mutation.
- `scene_cut`: scene-based cuts, useful for office/subway/room narratives.
- `error_system`: system messages, access failures, retries, and denial loops as structure.
- `body_memory`: body reactions as section logic.
- `through_composed`: minimal repetition with one returning echo phrase.

Default behavior: recommend the most stable executable route. When innovation is requested or necessary, provide an optional experimental variant and explain how it can still be fed to Suno.

## AI Output Density

Default output mode is `stage_fit`.

- Diagnosis can be longer.
- Hook Lab must be short and option-based.
- Structure Lab is medium detail.
- Lyrics Draft can be complete but sectioned.
- Suno Prompt Lab must be highly structured and copyable.
- Generation Review must be corrective and concise.
- Asset Organizer must be checklist-based.

Other modes:

- `deep_analysis`: longer producer analysis.
- `cards_only`: compact artifact cards and next actions.

## Artifact Lifecycle

AI-generated artifacts start as pending. The user can:

- accept
- lock
- discard
- set as current

Only accepted and locked artifacts enter the durable creative record. Locked artifacts are retained permanently.

## V1 Frontend Shape

The frontend is a Chinese workspace:

- Left: EP project selector, song list, and stage status.
- Center: current stage producer session and pending artifacts.
- Right: accepted artifacts, locked milestones, versions, and current working material.
- Drawer: advanced song archive/form editor.

Visual direction:

- Foundation: creative AI studio.
- Light identity layer: `GROWING UP.EXE` system state, access failure, background process, version residue.
- Avoid heavy CRT, heavy cyberpunk, visual noise, and novelty skins.

## Asset Bundle

V1 asset export includes:

- `song.md`
- `suno_prompt.md`
- `generation_reviews.md`
- `assets_manifest.json`
- `lyrics.txt`
- `notes_for_cubase.txt`
- `uploads/` copied uploaded files

`guide.mid` is not generated by default. It can be added later only when explicitly requested.

## Acceptance Checklist

Manual frontend acceptance:

- Open the homepage and see a Chinese V1 workspace.
- Create a new local EP project and see it selected.
- Create a new song inside that project.
- Select `访问失败`.
- See current stage status.
- Start the current stage.
- Receive human-readable AI response plus pending artifacts.
- Accept an artifact and see it appear in the right-side board.
- Lock an artifact and see it become permanent.
- Generate no more than three Suno Prompt Pack options.
- See one prompt pack recommended.
- Log one Suno generation review with text, scores, and uploaded files.
- Export a production asset bundle.

Automated API acceptance:

- Health endpoint returns ok.
- Seed data includes `访问失败`.
- EP projects can be listed and created.
- Song list can be filtered by EP project.
- Song stage can be updated with user confirmation.
- Session endpoint returns structured artifacts.
- Artifact accept/lock/discard transitions work.
- Suno Prompt Pack endpoint returns max three options and one recommendation.
- Generation review can be saved.
- Asset bundle export returns a zip containing the expected manifest and markdown files.
