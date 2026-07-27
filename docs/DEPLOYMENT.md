# Deployment

The app deploys as two independent services: the FastAPI backend (Docker) and
the React/Vite frontend (static site). Configs are already in this repo —
you just need accounts on the two platforms and to run through the steps
below. Neither Claude nor any automated tool can create these accounts or
deploy on your behalf.

## 1. Backend → Render

1. Push this repo to GitHub (if you haven't already).
2. In Render: **New → Blueprint**, point it at this repo. It will pick up
   [`render.yaml`](render.yaml) automatically.
3. Render will prompt for the three secret env vars marked `sync: false`:
   - `GITHUB_TOKEN` — a GitHub personal access token (no special scopes
     needed for public repos)
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
4. Deploy. Render builds `backend/Dockerfile` with the repo root as build
   context (needed so `feature_config.py` is available — see the comment
   at the top of that Dockerfile).
5. Note the deployed URL, e.g. `https://repo-quality-backend.onrender.com`
   — you'll need it for the frontend env vars below.

Alternative: Fly.io or Railway both support "deploy from Dockerfile"
directly; point them at `backend/Dockerfile` with build context `.` the
same way.

## 2. Frontend → Vercel

1. In Vercel: **New Project**, import this repo, set **Root Directory** to
   `frontend`.
2. Vercel auto-detects [`frontend/vercel.json`](frontend/vercel.json) for
   the build command/output dir and the SPA rewrite rule.
3. Set these env vars in the Vercel project settings:
   - `VITE_API_URL` — the Render backend URL from step 1.5
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
4. Deploy.

## 3. CORS

`backend/main.py` currently allows all origins (`allow_origins=["*"]`).
That's fine to ship the demo, but once you have a real frontend URL,
consider narrowing it to just that origin.

## 4. Badge

Once deployed, the quality badge is embeddable from any repo's README:

```md
![repo quality](https://your-backend-url/badge/OWNER/REPO)
```
