# Demo Deployment

This project has two deploys:

- Backend: FastAPI from the repo root
- Frontend: Next.js from `dashboard/`

This guide keeps `data/tracker.db` in the repo so the hosted app matches the local demo dataset.
The deployed app should use a trimmed copy at `data/tracker-demo.db` so it fits in GitHub.

## 1. Push To GitHub

From the repo root:

```bash
git init
git add .
git commit -m "Initial demo deploy"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/startup-tracker.git
git push -u origin main
```

## 2. Deploy Backend On Railway

Create a new Railway project from the GitHub repo.

Use these settings:

- Root directory: repo root
- Start command: `uvicorn api.app:app --host 0.0.0.0 --port $PORT`

Railway should install Python dependencies from `requirements.txt`.
Add this environment variable on Railway:

- `TRACKER_DB_PATH=data/tracker-demo.db`

After deploy, copy the backend URL.

## 3. Deploy Frontend On Vercel

Import the same GitHub repo into Vercel.

Use these settings:

- Root directory: `dashboard`
- Framework preset: Next.js
- Environment variable:
  - `NEXT_PUBLIC_API_URL=https://YOUR-RAILWAY-URL`

Deploy and open the Vercel URL.

## 4. Notes

- `data/tracker-demo.db` is intentionally committed in demo mode.
- `data/tracker.db-shm` and `data/tracker.db-wal` are ignored.
- If backend data looks stale, regenerate `data/tracker-demo.db` from your local database and push again.
