# EP Creative OS

EP Creative OS is a local FastAPI MVP for concept EP writing, Suno prompt preparation, lyric/version iteration, and Cubase handoff exports.

## Features

- EP state editor with seeded concept EP: `GROWING UP.EXE`
- Song CRUD with lyrics, concept, prompt, notes, BPM, and direction fields
- Creative chat endpoint for DeepSeek OpenAI-compatible chat completions
- Local Hook Engine that works without an API key
- Suno Style Prompt and Lyrics Prompt generator
- Song version snapshots and unified diffs
- Cubase bridge ZIP export with JSON, TXT, CSV, real MIDI files, and MusicXML skeleton
- Simple Suno MIDI upload metadata parser
- Minimal HTML + JS frontend at `/`
- Pytest smoke tests

## Run Locally

```bash
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

On Windows PowerShell, use:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\uvicorn app.main:app --reload
```

## DeepSeek

Set `DEEPSEEK_API_KEY` in `.env` to enable `/api/chat`. Without a key, the app still runs and all local CRUD, Hook, Suno prompt, versioning, import, and export flows remain usable.

## Tests

```bash
pytest
```
