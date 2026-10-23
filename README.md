# ⚡ Work Productivity AI Agent

Plan your day as tasks, track progress through the day, and get an end-of-day productivity report written by Claude.

**Live:** https://productivity-agent-three.vercel.app

## Architecture

| Part | Tech | Location |
|---|---|---|
| Web UI | Single-page HTML + vanilla JS | `public/index.html` |
| API | FastAPI (Python) on Vercel Functions | `api/index.py` |
| Database | Neon Postgres (via Vercel Marketplace) | `DATABASE_URL` |
| AI report | Anthropic API | `ANTHROPIC_API_KEY` |

`vercel.json` routes `/api/*` to the FastAPI app and `/` to the UI. Both are served from the same domain, so no CORS setup is needed.

The `tasks` table is created automatically on the first API cold start.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/tasks?date=YYYY-MM-DD` | List tasks for a date (defaults to today) |
| `POST` | `/api/tasks` | Create a task: `{title, estimated_hours, date?, initial_notes?}` |
| `GET` | `/api/tasks/{id}` | Get one task |
| `PATCH` | `/api/tasks/{id}` | Update any of `{actual_hours, status, percentage_done, update_notes}` |
| `DELETE` | `/api/tasks/{id}` | Delete a task |
| `POST` | `/api/report?date=YYYY-MM-DD` | Generate the AI productivity report for a date |

`status` is one of `Pending`, `In Progress`, `Completed`, `Blocked`. `percentage_done` is 0–100.

Interactive API docs are at http://localhost:8000/docs when running locally with uvicorn (see below).

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Pull DATABASE_URL and other env vars from Vercel into .env.local
vercel link
vercel env pull

# Add your Anthropic key to .env.local for the report endpoint
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env.local
```

Run the API:

```bash
set -a; source .env.local; set +a
uvicorn api.index:app --reload
```

To run the UI and API together with the production routing, use `vercel dev` instead.

## Deployment

```bash
vercel deploy          # preview
vercel deploy --prod   # production
```

Required environment variables in Vercel:

- `DATABASE_URL`: set automatically by the Neon integration
- `ANTHROPIC_API_KEY`: add with `vercel env add ANTHROPIC_API_KEY production`

## Legacy local tools

These predate the web app and still use a local SQLite file (`productivity.db`), not Neon:

- `app.py`: Streamlit UI (`pip install streamlit && streamlit run app.py`). Generates reports via the `claude` CLI.
- `productivity_cli.py`: terminal menu version, also using the `claude` CLI.
- `agent.py`: in-memory demo of the agent using the Anthropic SDK.
