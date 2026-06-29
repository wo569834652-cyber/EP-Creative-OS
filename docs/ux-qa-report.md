# EP Creative OS V1 UX QA Report

This report records the user-experience QA pass that drove the current V1 revisions.

## QA Panel

Four independent review roles were used:

- New user evaluator: tested whether a first-time user can create a project and understand the first useful action.
- Music creator workflow evaluator: checked whether the flow can actually advance an EP from concept toward Suno generation and review.
- Information architecture and copy evaluator: checked labels, empty states, action consequences, and whether terms like `Artifact` leak into user-facing decisions.
- Frontend interaction and visual evaluator: checked responsive layout, scroll behavior, prompt visibility, and whether important controls are reachable.

## Findings

- New project creation was blocked by a browser `prompt()` flow that was not reliable in the target environment.
- `生成 Suno Prompt 包` returned a success message, but the actual `Style Prompt` and `Lyrics Prompt` were not clearly visible or copyable.
- Users could click `进入下一阶段` while creative outputs were still pending, which made the workflow feel arbitrary.
- The right-side `CURRENT` board showed `Artifact #id`, which was technically correct but useless for a creator.
- The original stage output overfit the seed song `访问失败`; new songs inherited the wrong diagnosis and structure logic.
- The interface did not explain what the current stage required before advancing.
- Uploaded assets were stored, but users had no clear visible list of what had been archived.
- Tablet and mobile layouts used nested fixed-height scroll areas that made the page feel locked.

## Changes Made

- Replaced browser prompt project creation with in-page `新建 EP` and `新建歌曲` modals.
- Added a current-stage guide with description, completion conditions, and readiness status.
- Made pending creative outputs the central handoff: they appear in `待确认创作产物` and must be saved, discarded, locked, or set current.
- Added frontend and backend blocking when pending creative outputs exist before stage advancement.
- Expanded Suno Prompt Pack cards so the recommended pack is visible by default and alternate packs are collapsible.
- Added direct copy actions for `Style Prompt`, `Lyrics Prompt`, and the recommended full pack.
- Replaced `Artifact #id` in the current board with `Suno Prompt：primary（推荐）`.
- Added a visible uploaded asset list.
- Changed generic song diagnosis, structure, and lyrics generation so new songs are no longer forced into the `访问失败` concept.
- Kept a stable default route while preserving optional experimental structure routes.
- Changed responsive CSS below 1180px to use natural page scrolling instead of locked internal scroll containers.
- Added an inline favicon to remove browser 404 noise during QA.

## Verification

Automated checks:

- `python -m compileall app`
- `node --check app/static/app.js`
- `pytest -q`
- `git diff --check`

Browser QA covered:

- Desktop viewport: create EP, create first song, run diagnosis, block advancement while output is pending, save output, advance to next stage.
- Full workflow: diagnosis -> Hook -> structure -> lyrics -> Suno Prompt Lab -> generate prompt pack -> set recommended prompt as current.
- Prompt visibility: verified `Style Prompt`, `Lyrics Prompt`, `复制推荐整套`, and current prompt label are visible.
- Responsive viewport: verified mobile width has no horizontal overflow and no console errors.

## Remaining Product Boundaries

- V1 does not analyze audio directly.
- V1 does not generate a Cubase-native project file.
- V1 uses deterministic local stage outputs and deterministic Suno prompt rules; DeepSeek can be integrated for conversational assistance, but prompt methodology is encoded in code rather than researched at runtime.
