# Pepys Diary Viewer

A lightweight viewer for *The Shorter Pepys* with per-day entries, summaries, and entity sidebar. Served by a Flask app packaged with Nix.

## Prerequisites
- Nix (flake-enabled)

## Quick start (Nix)
```bash
# build & run
OPENAI_API_KEY=sk-your-key PORT=8000 nix run .#
# then open http://localhost:8000
```

> Note: The summaries call OpenAI. If you run without a valid key, the app starts but summary requests will fail; the UI will fall back to local truncation.

## Sample .envrc
Create a `.envrc` (or copy from `.envrc.sample`) with a dummy token:
```bash
# .envrc.sample
export OPENAI_API_KEY="sk-dummy"
export PORT=8000
export OPENAI_MODEL="gpt-4o-mini"
```

Then move/rename it to `.envrc` and allow direnv:
```bash
cp .envrc.sample .envrc
# if you use direnv
# direnv allow
```
Replace `sk-dummy` with your real key when you want live summaries.

## What’s included
- `diary_by_date/` — one file per diary date
- `site/` — static assets (`index.html`, `diaries.json`, `entities.json`)
- `app.py` — Flask server (serves `site/` and `/summarize`)
- `flake.nix` — Nix flake packaging the app as `pepys-server`

## Development notes
- Nix build:
  ```bash
  nix build .# --keep-failed -L
  ```
- Run with a timeout/oneshot check (no summaries):
  ```bash
  OPENAI_API_KEY=sk-dummy nix run .#
  ```

## Using the app
- Navigate dates via the picker or arrow buttons.
- Summaries: choose 10-word / 100-word / half-length (LLM) or full text.
- Entities sidebar: shows detected entities for the current entry.

## Caveats
- Summaries require network access and a valid OpenAI API key.
- Entity extraction in the UI is heuristic; for higher fidelity, integrate the prebuilt `site/entities.json` or a richer NER backend.
