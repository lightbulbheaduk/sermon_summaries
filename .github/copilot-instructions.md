<!-- Copilot / AI agent instructions for the sermon_summaries repo -->
# Quick Agent Guide — sermon_summaries

Purpose: orient an AI coding agent (or a new human dev) to the pipeline, conventions, and safe change boundaries so you can implement fixes and features quickly.

Big picture
- `src/main.py` is the pipeline orchestrator. It: finds new RSS episodes, downloads audio, transcribes, summarises (produces strict JSON), saves artifacts under `data/episodes/<id>/`, and renders the static site into `docs/`.
- Key modules: `src/feed_watcher.py`, `src/downloader.py`, `src/transcriber.py`, `src/summarizer.py`, `src/publisher.py`, `src/utils.py`.
- Site templates are in `templates/` and rendered by `publisher.publish_site` to `docs/` (GitHub Pages-ready). `data/state.json` stores processed episode ids.

Data & artifact conventions (important)
- Episode directory layout: `data/episodes/<id>/meta.json`, `transcript.json` (object with `text`), `summary.json` (the summariser's JSON). Code and templates rely on these filenames.
- `summary.json` schema (normalised by `summarizer.extract_key_info`):
  - `overall_theme` (string)
  - `quotes` (array of strings)
  - `bible_passages` (array of strings)
  - `follow_on_questions` (array of strings)
  - `further_bible_passages` (array of objects `{ref, rationale}`)
- `prompt.txt` contains the user prompt used by `summarizer.extract_key_info`. The summarizer expects the model output to be valid JSON (code includes fallbacks and a regex-based recovery).

Runtime & developer workflows
- Install deps: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`.
- Required external tool: `ffmpeg` (checked in `src/transcriber.py`). If missing, transcribing will raise.
- Provide OpenAI key via env var: `export OPENAI_API_KEY=...` (do not commit keys).
- Run the full pipeline locally: `python src/main.py` (reads `config.yml` or falls back to `config.example.yml`).
- Run a single component for debugging:
  - Transcribe: `python -c "from src.transcriber import transcribe_audio; print(transcribe_audio('path/to/file.mp3', 'tmp', model='whisper-1', segment_seconds=600))"`
  - Summarize a transcript: `python -c "from src.summarizer import extract_key_info; print(extract_key_info(open('transcript.txt').read(), open('prompt.txt').read(), model='gpt-4o-mini', temperature=0.2))"`

Patterns & conventions for changes
- Keep file layout/names stable: `meta.json`, `transcript.json`, `summary.json` are consumer-facing for `publisher` and the static site.
- Summariser output must be JSON-like; code depends on keys being present and normalises types. If changing the schema, update `publisher` and templates under `templates/`.
- Downloads are guarded by `pipeline.max_download_mb` in `config.yml`. Respect this when altering downloader logic.
- Audio is chunked by `pipeline.segment_seconds`. `transcriber` uses `ffmpeg` + OpenAI audio endpoints; maintain retry semantics via `tenacity` if modifying.

Integration points & external dependencies
- OpenAI API: used in `transcriber` and `summarizer` via the `openai` SDK (`from openai import OpenAI`). Models configured in `config.yml` under `openai`.
- Network: feeds (RSS), external audio URLs (download), and bible links (rendered via `publisher` filter). Keep network calls robust and retried where appropriate.

Logging, errors and safe cleanup
- Logging is configured in `src/utils.setup_logging()` and writes to `logs/pipeline.log` and stdout. Use this file when debugging CI runs.
- Temp audio and chunk directories are cleaned (see `main` finally block). When adding new temp directories, follow the same cleanup pattern.

Search tips and examples
- To find how episodes are loaded: inspect `src/publisher.py::load_episodes` and `templates/episode.html` (fields used there reflect JSON keys).
- To see the prompt and strict output expectations: open `prompt.txt` (describes required JSON keys and British English spellings).

CI / GitHub Actions
- Workflow: `.github/workflows/pipeline.yml` — runs daily via cron and supports manual dispatch.
- What it does: checks out the repo, sets up Python, installs `ffmpeg`, installs dependencies, runs the pipeline (`python -m src.main`), then commits `data/` and `docs/` back to the repository when changes appear.
- Important details:
  - The runner requires a GitHub Secret `OPENAI_API_KEY` (exposed as `secrets.OPENAI_API_KEY`).
  - The workflow sets `permissions: contents: write` to allow committing output files.
  - Commits from Actions use the message `Update data and site [skip ci]` to avoid re-triggering the job.
  - Because the workflow commits, avoid pushing incompatible schema changes without local testing — the action may push site files that break templates if schema and templates disagree.


If you change the summariser JSON format
- Update `src/summarizer.py` normalization first, then `templates/` and `src/publisher.py::load_episodes` to avoid runtime template errors.

When in doubt
- Run `python src/main.py` locally with a single feed in `config.yml` and check `data/episodes/` and `docs/` outputs.

Questions? If any of the above is unclear, tell me which component or workflow you want expanded and I will update this file.
