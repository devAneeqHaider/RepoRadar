# RepoRadar — Frontend

AI-powered GitHub repository architect. Paste a repo URL and RepoRadar clones
it, maps its module/class architecture as an interactive graph, flags code
smells, and generates an AI onboarding guide.

This is the **React (Vite) frontend**. The Django REST backend lives in
`../backend/` and implements API v1.

## Prerequisites

- Node.js 18+ (20 recommended) and npm
- The RepoRadar backend running (default `http://localhost:8000`) for real data

## Quick start

```bash
# 1. Install dependencies
npm install

# 2. (Optional) configure the API base URL
cp .env.example .env   # then edit VITE_API_URL if needed

# 3. Start the dev server (with the backend running)
npm run dev            # -> http://localhost:5173
```

During development the client calls relative `/api/...` paths and the Vite dev
server proxies them to `http://localhost:8000`, so no CORS configuration is
needed.

## Scripts

| Script          | What it does                                  |
| --------------- | --------------------------------------------- |
| `npm run dev`   | Start the Vite dev server with HMR            |
| `npm run build` | Type-safe production build into `dist/`      |
| `npm run preview` | Serve the production build locally for a check |

## Environment variables

| Variable        | Default                | Purpose                                                   |
| --------------- | ---------------------- | --------------------------------------------------------- |
| `VITE_API_URL`  | *(unset — proxy mode)* | Base URL prefix for API calls. Leave unset in dev so the Vite proxy handles `/api`; set it in production when the frontend is served separately from the backend, e.g. `VITE_API_URL=https://api.example.com`. |

Vite reads `.env` at dev-server/build start — restart after changing it.

## Project structure

```
reporadar-frontend/
├── index.html                  # HTML shell
├── vite.config.js              # React plugin + /api -> localhost:8000 proxy
├── Dockerfile                  # multi-stage: node:20 build -> nginx serve
├── .env.example                # documented VITE_API_URL example
├── package.json
└── src/
    ├── main.jsx                # React entry point
    ├── App.jsx                 # Router, header/footer layout, 404
    ├── index.css               # hand-crafted dark dev-tool theme
    ├── api/
    │   └── client.js           # fetch wrapper + API v1 functions
    ├── components/
    │   ├── RepoForm.jsx        # GitHub URL form + validation
    │   ├── JobProgress.jsx     # job polling, animated progress bar
    │   ├── GraphView.jsx       # force-directed architecture graph
    │   ├── SmellList.jsx       # severity-filtered code smells
    │   ├── GuideView.jsx       # rendered AI onboarding guide (markdown)
    │   └── StatCards.jsx       # Files / Modules / Classes / Functions
    └── pages/
        ├── Home.jsx            # hero, form, recently-analyzed repos
        ├── RepoDetail.jsx      # header + Overview | Graph | Smells | Guide tabs
        └── JobPage.jsx         # /job/:jobId progress route
```

## API contract (v1)

| Method | Path                    | Notes                                   |
| ------ | ----------------------- | --------------------------------------- |
| POST   | `/api/analyze/`         | Body `{"repo_url": "..."}` → `202 {"job_id"}` |
| GET    | `/api/jobs/<uuid>/`     | Job status: `pending, downloading, parsing, analyzing, ai, done, failed` |
| GET    | `/api/repos/`           | List of analyzed repositories           |
| GET    | `/api/repos/<id>/`      | Repo detail incl. `stats`               |
| GET    | `/api/repos/<id>/graph/`| `{ nodes, edges }`                      |
| GET    | `/api/repos/<id>/smells/`| Code-smell findings                    |
| GET    | `/api/repos/<id>/guide/`| `{ markdown }` onboarding guide         |
| GET    | `/api/repos/<id>/report/`| Downloadable PDF analysis report        |

## Docker

```bash
docker build -t reporadar-frontend .
docker run -p 8080:80 reporadar-frontend
```

To point the production bundle at a remote API, pass it as a build arg:

```bash
docker build --build-arg VITE_API_URL=https://api.example.com -t reporadar-frontend .
```
