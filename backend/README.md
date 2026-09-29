# RepoRadar — Backend

AI-powered GitHub repository architect. Paste a public repo URL, get back a
dependency graph, code-smell report, and an onboarding guide.

**Stack:** Django 5 + Django REST Framework + Celery + Redis + PostgreSQL.
AI features use the **free** Google Gemini API tier and degrade gracefully —
if `GEMINI_API_KEY` is missing, you still get factual guides and the static
smell suggestions; nothing crashes.

> Frontend lives in `../frontend/` (React + Vite). This README covers the backend only.

---

## 1. Manual setup

**Prerequisites:** Python 3.12+, PostgreSQL, Redis.

```bash
# 1. Create the database and user
sudo -u postgres psql -c "CREATE USER reporadar WITH PASSWORD 'reporadar';"
sudo -u postgres psql -c "CREATE DATABASE reporadar OWNER reporadar;"

# 2. Start Redis (separate terminal or background)
redis-server

# 3. Virtual environment + dependencies
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Environment
cp .env.example .env
# edit .env if needed; GEMINI_API_KEY is optional (see section 3)

# 5. Migrate
python manage.py migrate
```

### Run (two terminals)

```bash
# Terminal 1 — API server
source .venv/bin/activate
python manage.py runserver
```

```bash
# Terminal 2 — Celery worker (runs the analysis pipeline)
source .venv/bin/activate
celery -A config worker --loglevel=info
```

The API is then at `http://localhost:8000/api/`.

### Tests (no Postgres/Redis needed)

```bash
source .venv/bin/activate
python manage.py test
```

When `test` is in `sys.argv`, Django automatically uses in-memory SQLite.

---

## 2. API contract (v1)

### Analyze a repository

```bash
curl -s -X POST http://localhost:8000/api/analyze/ \
  -H 'Content-Type: application/json' \
  -d '{"repo_url": "https://github.com/psf/requests"}'
# -> 202 {"job_id": "<uuid>"}
```

### Poll the job

```bash
curl -s http://localhost:8000/api/jobs/<uuid>/
# -> {"job_id","status","progress":0-100,"message","error","repository_id"}
# status: pending|downloading|parsing|analyzing|ai|done|failed
```

### List analyzed repos

```bash
curl -s http://localhost:8000/api/repos/
# -> [{"id","owner","name","url","language","stars","analyzed_at"}]
```

### Repo detail (+ stats)

```bash
curl -s http://localhost:8000/api/repos/1/
# -> full detail + {"file_count","module_count","class_count",
#    "function_count","top_languages"} in "stats"
```

### Dependency graph

```bash
curl -s http://localhost:8000/api/repos/1/graph/
# -> {"nodes":[{"id","label","type":"module|class","path"}],
#     "edges":[{"from","to","type":"imports"}]}
```

### Code smells

```bash
curl -s http://localhost:8000/api/repos/1/smells/
# -> [{"id","type","severity":"high|medium|low","title","file","line",
#      "detail","suggestion"}]
```

### Onboarding guide

```bash
curl -s http://localhost:8000/api/repos/1/guide/
# -> {"markdown": "..."}
```

---

## 3. Free Gemini key (optional)

1. Go to [Google AI Studio](https://aistudio.google.com/) and sign in.
2. Click **Get API key** → create one (free tier, no card required).
3. Put it in `.env`: `GEMINI_API_KEY=your-key-here`
4. Restart the Celery worker.

Without it, guides are generated from real analysis facts with a note that
the AI enrichment is disabled — the API shape never changes.

---

## 4. Project layout

```
backend/
├── config/                 # Django project: settings, urls, celery, wsgi, asgi
├── repositories/           # Repository + AnalysisJob models
├── analyzer/
│   ├── services/
│   │   ├── github_client.py   # tarball download (50 MB cap, safe extract)
│   │   ├── walker.py          # file walk + language detection
│   │   ├── python_parser.py   # AST: imports, classes, functions, call edges
│   │   ├── graph_builder.py   # nodes/edges for the frontend
│   │   └── smell_detector.py  # circular imports, god modules, long fns, …
│   ├── tasks.py            # Celery pipeline run_analysis (5 stages)
│   └── tests/              # parser + smell detector unit tests
├── ai_engine/
│   └── services/
│       ├── gemini_client.py   # GeminiProvider (SDK with urllib REST fallback)
│       ├── prompts.py         # ALL prompt strings live here
│       ├── guide_generator.py # onboarding guide (+ static fallback)
│       └── smell_explainer.py # batched LLM smell explanations (+ fallback)
├── api/                    # serializers, thin views, urls (contract v1)
├── requirements.txt
├── Dockerfile
└── .env.example
```

**Notes**

- Only **public** repositories are supported; no GitHub token is used.
- Downloads are capped (~50 MB tarball, 2000 files) and archives are
  extracted with path-traversal protection.
- Views are thin — every bit of business logic lives in `services/`.
