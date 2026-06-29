# EP Creative OS

EP Creative OS is a local V1 creative production workspace for pushing concept EP projects from scattered ideas into usable hooks, Suno prompt packs, generation review logs, and organized production assets.

The current V1 focus is not a generic CRUD demo. It is a stage-based writing and production flow:

`歌曲诊断 -> Hook 实验室 -> 结构实验室 -> 歌词草稿 -> Suno Prompt 实验室 -> 生成复盘 -> 素材整理`

## V1 Highlights

- Chinese three-column workspace: song navigator, producer session, artifact/version board
- Local EP project switcher and new project/new song flow
- Seed EP: `GROWING UP.EXE`
- Main acceptance song: `访问失败`
- Stage-based producer sessions
- Pending/accepted/locked artifact lifecycle
- Creative versions based on accepted artifacts
- Deterministic Suno Prompt Engine with up to three packs and exactly one recommendation
- Generation review log with text feedback and scoring
- Asset uploads stored on disk and indexed in SQLite
- Asset bundle export with markdown notes, lyrics, prompts, reviews, manifest, and uploads
- DeepSeek OpenAI-compatible client using `deepseek-v4-pro` by default

## Run Locally

```bash
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

## DeepSeek

Set `DEEPSEEK_API_KEY` in `.env`.

Defaults:

```env
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_CONTEXT_WINDOW=1000000
```

Without a key, the local V1 workflow still works through deterministic stage outputs and the Suno Prompt Engine.

## Tests

```bash
pytest
```

## V1 Docs

- `docs/v1-product-spec.md`
- `docs/v1-data-model.md`
- `docs/v1-ai-contract.md`
- `docs/v1-frontend-spec.md`
- `docs/v1-implementation-plan.md`
