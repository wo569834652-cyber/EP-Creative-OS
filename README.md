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
- Visible version snapshots with one-click restore to any previous song state
- Deterministic Suno Prompt Engine with up to three packs and exactly one recommendation
- Generation review log with text feedback and scoring
- Asset uploads stored on disk and indexed in SQLite
- Asset bundle export with markdown notes, lyrics, prompts, reviews, manifest, and uploads
- DeepSeek OpenAI-compatible client using `deepseek-v4-pro` by default

## AI Involvement

The main production flow now tries to use DeepSeek first in the creative stages where AI can materially move the song forward:

- `歌曲诊断`: AI acts as producer and identifies the song's EP function, biggest problem, risks, and next stage.
- `Hook 实验室`: AI generates and scores singable Hook candidates.
- `结构实验室`: AI recommends a stable route and optional innovative routes for the song.
- `歌词草稿`: AI writes a real full lyric draft. This is not the Suno `Lyrics Prompt`.
- `生成复盘`: AI reads your Suno feedback and scores, then recommends the next revision target.

Lyrics drafts now pass through a local quality gate after the DeepSeek call. The app scores hook preservation, concrete song material, section readability, cliche risk, and prompt leakage. Weak drafts trigger one automatic AI rewrite, and the resulting artifact shows a visible quality score plus the main issues.

If DeepSeek is unavailable or returns invalid structured output, the app falls back to local deterministic drafts and marks the artifact as `本地草稿` in the UI. AI-generated artifacts are marked as `AI 生成`.

`Suno Prompt 实验室` remains rule-led for quality control: it uses the accepted Hook, structure route, accepted lyrics, song concept, EP function, mood, and BPM to build copyable `Style Prompt` and `Lyrics Prompt` packs. Each pack exposes a style specificity score and quality checks so the prompt does not collapse into a generic style template.

## Recommended Local Use

On Windows, you do not need to type terminal commands for normal use:

1. Double-click `打开 EP Creative OS.bat`.
2. Wait for the browser to open `http://127.0.0.1:8000`.
3. Use the app normally.
4. Close it from the top-right `关闭服务` button in the webpage, or double-click `关闭 EP Creative OS.bat`.

The first launch creates `.venv` and installs `requirements.txt`, so it may take longer. Later launches should be much faster.

## Run Locally

Manual development mode:

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

## 中文使用路径

打开本地页面后，按这个顺序使用：

1. 在左侧选择 EP；需要新项目时点 `新建 EP`，填写 EP 名称、一句话概念和第一首歌。
2. 选择一首歌后，看中间的 `当前步骤`。这里会显示本阶段要完成什么，以及现在能不能进入下一阶段。
3. 点 `生成本阶段建议`。生成结果会进入 `待确认创作产物`，不是直接隐藏到数据库里。
4. 对每个待确认产物选择 `保存为可用版本`、`不采用`、`锁定为关键版本` 或 `设为当前...`。
5. 处理完待确认产物后，再点 `进入下一阶段`。
6. 到 `歌词草稿` 阶段时，DeepSeek 可用会生成真正的完整歌词；不可用时会标记为本地草稿。
7. 到 `Suno Prompt 实验室` 后点 `生成可复制到 Suno 的提示词`。系统最多生成三套，默认推荐 `primary`，并直接显示 `Style Prompt`、`Lyrics Prompt` 和复制按钮。
8. 在 Suno 生成后，把听感和评分填入 `生成复盘`；DeepSeek 可用会判断下一轮优先改哪里。音频或 MIDI 可以上传，最后用 `导出素材包` 整理制作资料。

关键规则：

- 有待确认产物时，系统会阻止进入下一阶段，避免创作决定丢失。
- `生成可复制到 Suno 的提示词` 会检查 Hook、结构路线和歌词草稿是否齐全；缺材料时会提示先补哪一项。
- 右侧 `版本记录` 每张卡都可以 `查看快照`，也可以 `回溯到此版本`。回溯不会删除历史，而是恢复该快照并新增一条回溯版本。
- V1 不伪装成音频分析器；Suno 结果复盘以你的文字反馈、评分和上传素材为准。

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
- `docs/ux-qa-report.md`
