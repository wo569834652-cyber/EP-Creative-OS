# EP Creative OS V1 Frontend Spec

## Design Direction

The UI is a Chinese creative AI studio with a light `GROWING UP.EXE` system identity.

It should feel:

- focused
- calm
- musical
- version-aware
- practical for repeated writing sessions

It should not feel:

- like a generic admin panel
- like a marketing page
- like a heavy retro CRT skin
- like a pure chat clone

## Layout

V1 uses a three-column workspace.

## Left Column: EP Navigator

Content:

- EP title and one-line concept
- project selector
- new project action
- new song action
- song list
- each song's current stage
- selected song highlight
- quick status badges: pending, accepted, locked

Primary purpose:

- choose the song
- understand where each song is in the EP process

## Center Column: Producer Session

Content:

- selected song header
- stage progress
- stage goal
- output mode selector
- user goal/message input
- start current stage button
- AI response
- pending artifact cards

Primary purpose:

- run the current stage
- review AI output
- accept/discard artifacts
- confirm stage advancement

## Right Column: Version and Artifact Board

Content:

- current locked hook
- current structure route
- current prompt pack
- accepted artifacts
- locked milestones
- recent versions
- export asset bundle button

Primary purpose:

- preserve creative decisions
- compare what has been accepted
- prepare production handoff

## Advanced Song Archive Drawer

Accessible from selected song header.

Fields:

- title
- function in EP
- concept
- emotional goal
- BPM
- genre direction
- language plan
- lyrics
- style prompt
- lyrics prompt
- notes

This editor is not the main experience. It is for direct correction and recovery.

## Chinese UI Requirements

All visible frontend labels should be Chinese.

Backend values may remain English:

- `hook_lab`
- `suno_prompt_pack`
- `accepted`

Frontend display maps them:

- `hook_lab` -> `Hook 实验室`
- `suno_prompt_pack` -> `Suno Prompt 包`
- `accepted` -> `已接受`

## Stage Display Names

- `diagnosis`: `歌曲诊断`
- `hook_lab`: `Hook 实验室`
- `structure_lab`: `结构实验室`
- `lyrics_draft`: `歌词草稿`
- `suno_prompt_lab`: `Suno Prompt 实验室`
- `generation_review`: `生成复盘`
- `asset_organizer`: `素材整理`
- `parked`: `暂停`
- `done`: `完成`

## Artifact Card Actions

Pending card:

- `接受`
- `锁定`
- `丢弃`
- `设为当前`

Accepted card:

- `锁定`
- `设为当前`

Locked card:

- show persistent milestone styling

## Design QA

Implementation must be checked in browser with:

- desktop viewport
- narrower responsive viewport
- no broken Chinese text
- no overlapping controls
- clear three-column hierarchy
- readable artifact cards

Use browser QA tooling rather than relying only on code inspection.

## Visual System

Suggested palette:

- warm off-white workspace background
- dark ink text
- muted graphite panels
- teal/green for active progress
- red/pink accent for access failure or risk states
- amber for pending decisions

Avoid one-note palettes and heavy blue/purple gradients.

Shape:

- small radius panels and cards
- dense but readable spacing
- no nested decorative cards
- controls should feel like a tool, not a landing page

Typography:

- system sans-serif
- no viewport-scaled font sizes
- no negative letter spacing
- compact headings inside panels

## Empty and Error States

Must include Chinese states:

- `还没有会话，先运行当前阶段。`
- `这个 Artifact 已丢弃。`
- `DeepSeek API key 未配置，本地功能仍可使用。`
- `素材包导出失败，请检查文件是否仍存在。`
