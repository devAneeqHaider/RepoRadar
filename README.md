# RepoRadar — AI GitHub Repository Architect

Paste any public GitHub URL → RepoRadar downloads the repo, parses it with a real
AST engine, and gives you back an **interactive architecture graph**, a **code-smell
report**, an **AI-generated onboarding guide**, and a downloadable **PDF analysis
report**. No more week-long onboarding.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Django](https://img.shields.io/badge/Django-5.x-green)
![DRF](https://img.shields.io/badge/DRF-API-red)
![React](https://img.shields.io/badge/React-18-61dafb)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Celery](https://img.shields.io/badge/Celery-tasks-37814a)
![License](https://img.shields.io/badge/License-MIT-yellow)

## What it does

- **Architecture graph** — every Python module and class as nodes, real import
  edges between them, rendered as an interactive force-directed graph. Click a node
  to inspect it.
- **Code smells, deterministically** — circular imports (cycle detection on the
  import graph), god modules, long functions, dead private code, wildcard imports.
  Found by static analysis, not by asking an LLM to guess.
- **Onboarding guide** — an LLM writes the "new developer" docs: overview, tech
  stack, project structure, key modules, how to run, entry points. Falls back to a
  factual guide when no API key is set.
- **Job pipeline with live progress** — analysis runs in Celery; the UI polls and
  shows real stage progress (downloading → parsing → analyzing → AI → done).
- **PDF analysis report** — download repository metrics, architecture counts,
  language breakdown, code-smell findings, and the onboarding guide as a PDF.

## Architecture

```
 ┌──────────┐   POST /api/analyze/    ┌──────────┐   delay()   ┌───────────┐
 │  React   │ ─────────────────────▶ │ Django / │ ──────────▶ │  Celery   │
 │  (Vite)  │ ◀───────────────────── │   DRF    │ ◀────────── │  Worker   │
 └──────────┘   GET /api/jobs/<id>/   └────┬─────┘  results    └─────┬─────┘
       │            (poll 2s)              │                         │
       │   ┌─────────────────────────────┐│   ┌─────────────────────┘
       │   │        PostgreSQL           ││   │   download tarball
       └──▶│  Repository / AnalysisJob   ││   │   → walk + AST parse
           └─────────────────────────────┘│   │   → graph + smells
                                          │   │   → Gemini guide (optional)
           ┌─────────────────────────────┐│   └──▶ save to DB
           │        Redis (broker)       ││
           └─────────────────────────────┘┘
```

The key design decision: **deterministic analysis first, LLM second.** AST parsing,
import resolution, cycle detection and smell rules are plain Python — fast, free,
reproducible. The LLM only writes prose (the guide) and plain-English explanations
of findings. That is also why the app is fully useful with no API key at all.

## Tech stack

| Layer    | Tech                                                        |
|----------|-------------------------------------------------------------|
| Backend  | Django 5, Django REST Framework, Celery, Redis              |
| Database | PostgreSQL 16 (SQLite for tests)                            |
| Analysis | Python `ast`, hand-rolled import resolver, DFS cycle finder |
| AI       | Google Gemini (free tier), graceful no-key fallback         |
| Frontend | React 18, Vite, react-router-dom, react-force-graph-2d      |

## Quickstart — Docker (recommended)

```bash
# optional: richer AI guides with a free key from https://aistudio.google.com/apikey
export GEMINI_API_KEY=your_key_here

docker compose up --build
```

- Frontend → http://localhost:5173
- Backend API → http://localhost:8000/api/

Paste a repo URL (e.g. `https://github.com/pallets/flask`) and watch it analyze.

## Quickstart — manual

**Backend** (`backend/` — full details in `backend/README.md`):

```bash
createdb reporadar                       # + a user, or edit DATABASE_URL
redis-server &
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver               # terminal 1 → :8000
celery -A config worker --loglevel=info  # terminal 2
```

**Frontend** (`frontend/` — full details in `frontend/README.md`):

```bash
cd frontend
npm install
npm run dev                              # → :5173, proxies /api to :8000
```

**Tests** (backend, no services needed — uses in-memory SQLite):

```bash
cd backend && python manage.py test
```

## The free AI key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) → create a free key.
2. `export GEMINI_API_KEY=...` (compose) or add it to `backend/.env`.
3. Without a key, everything still works: the guide generator writes a factual
   guide from the analysis, and smells keep their static suggestions.

## Try it on

Good demo repos (small → large):

- `https://github.com/pallets/flask` — clean, well-structured
- `https://github.com/django/django` — big; watch the graph light up
- `https://github.com/psf/requests` — small, readable
- Your own repos — dogfood the smell detector before you push

## API (v1)

| Method | Path                        | Description                          |
|--------|-----------------------------|--------------------------------------|
| POST   | `/api/analyze/`             | `{"repo_url": "..."}` → `202 {"job_id"}` |
| GET    | `/api/jobs/<uuid>/`         | job status + progress 0–100          |
| GET    | `/api/repos/`               | analyzed repos                       |
| GET    | `/api/repos/<id>/`          | repo detail + stats                  |
| GET    | `/api/repos/<id>/graph/`    | `{nodes, edges}`                     |
| GET    | `/api/repos/<id>/smells/`   | code-smell findings                  |
| GET    | `/api/repos/<id>/guide/`    | `{"markdown": "..."}`                |
| GET    | `/api/repos/<id>/report/`   | downloadable PDF analysis report      |

Job statuses: `pending → downloading → parsing → analyzing → ai → done`
(`failed` on error, with message).

## Roadmap

- Multi-language deep analysis via tree-sitter (Python is deep today; other
  languages get file-level stats)
- "Request flow" tracer: pick an endpoint, get the call chain as a sequence diagram
- PR review mode: analyze a diff instead of a whole repo
- Change-impact view: "what breaks if I touch this module?"

## License

MIT — see [LICENSE](LICENSE).
