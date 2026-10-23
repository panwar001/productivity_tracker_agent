import os
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row

# Neon Postgres connection string, injected by the Vercel Neon integration.
# Locally, run `vercel env pull` to get it into .env.local.
DATABASE_URL = os.environ.get("DATABASE_URL")

app = FastAPI(title="Productivity Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str
    estimated_hours: float
    date: Optional[str] = None          # defaults to today
    initial_notes: Optional[str] = None


class TaskUpdate(BaseModel):
    actual_hours: Optional[float] = None
    status: Optional[str] = None        # Pending | In Progress | Completed | Blocked
    percentage_done: Optional[int] = None
    update_notes: Optional[str] = None


class Task(BaseModel):
    id: int
    date: str
    title: str
    estimated_hours: float
    actual_hours: float
    status: str
    percentage_done: int
    initial_notes: Optional[str]
    update_notes: Optional[str]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL env var not set")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id               SERIAL  PRIMARY KEY,
            date             TEXT    NOT NULL,
            title            TEXT    NOT NULL,
            estimated_hours  DOUBLE PRECISION NOT NULL,
            actual_hours     DOUBLE PRECISION DEFAULT 0.0,
            status           TEXT    DEFAULT 'Pending',
            percentage_done  INTEGER DEFAULT 0,
            initial_notes    TEXT,
            update_notes     TEXT
        )
    """)
    conn.commit()
    conn.close()


def row_to_task(row) -> Task:
    return Task(
        id=row["id"],
        date=row["date"],
        title=row["title"],
        estimated_hours=row["estimated_hours"],
        actual_hours=row["actual_hours"] or 0.0,
        status=row["status"] or "Pending",
        percentage_done=row["percentage_done"] or 0,
        initial_notes=row["initial_notes"],
        update_notes=row["update_notes"],
    )


# Initialise on module load (runs once per cold start on Vercel)
init_db()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def health():
    return {"status": "ok", "service": "Productivity Agent API"}


@app.get("/api/tasks", response_model=list[Task])
def list_tasks(date: Optional[str] = None):
    """Return all tasks for a given date (defaults to today)."""
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE date = %s ORDER BY id", (target_date,)
    ).fetchall()
    conn.close()
    return [row_to_task(r) for r in rows]


@app.post("/api/tasks", response_model=Task, status_code=201)
def create_task(body: TaskCreate):
    """Create a new task."""
    date = body.date or datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute(
        "INSERT INTO tasks (date, title, estimated_hours, initial_notes) VALUES (%s, %s, %s, %s) RETURNING *",
        (date, body.title, body.estimated_hours, body.initial_notes),
    ).fetchone()
    conn.commit()
    conn.close()
    return row_to_task(row)


@app.get("/api/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    """Fetch a single task by ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row_to_task(row)


@app.patch("/api/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, body: TaskUpdate):
    """Partially update a task (progress, status, hours, notes)."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    # Only update fields that were explicitly provided
    updates = {}
    if body.actual_hours is not None:
        updates["actual_hours"] = body.actual_hours
    if body.status is not None:
        valid = {"Pending", "In Progress", "Completed", "Blocked"}
        if body.status not in valid:
            conn.close()
            raise HTTPException(status_code=422, detail=f"status must be one of {valid}")
        updates["status"] = body.status
    if body.percentage_done is not None:
        if not 0 <= body.percentage_done <= 100:
            conn.close()
            raise HTTPException(status_code=422, detail="percentage_done must be 0–100")
        updates["percentage_done"] = body.percentage_done
    if body.update_notes is not None:
        updates["update_notes"] = body.update_notes

    if updates:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = %s",
            (*updates.values(), task_id),
        )
        conn.commit()

    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
    conn.close()
    return row_to_task(row)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    """Delete a task."""
    conn = get_conn()
    result = conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    conn.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")


@app.post("/api/report")
def generate_report(date: Optional[str] = None):
    """Generate an AI productivity report for the given date using the Anthropic SDK."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY env var not set")

    target_date = date or datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE date = %s ORDER BY id", (target_date,)
    ).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No tasks found for {target_date}")

    tasks_data = [dict(r) for r in rows]
    total_estimated = sum(t["estimated_hours"] for t in tasks_data)
    total_actual = sum(t["actual_hours"] or 0 for t in tasks_data)
    avg_completion = sum(t["percentage_done"] or 0 for t in tasks_data) / len(tasks_data)

    prompt = f"""You are an expert productivity coach.
Analyze today's task execution data and generate a structured Productivity Report.

Date: {target_date}
Overall Completion: {avg_completion:.1f}%
Total Hours Estimated: {total_estimated}h
Total Hours Logged: {total_actual}h

Tasks Data:
{json.dumps(tasks_data, indent=2)}

Please analyze:
1. **Productivity Score**: Grade (A+ to F) with reasoning.
2. **Key Accomplishments**: What went well today.
3. **Estimation vs Reality**: Analyze effort/time accuracy.
4. **Blockers & Distractions**: Identify key issues based on user notes.
5. **Actionable Suggestions for Tomorrow**: 2-3 specific improvements."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        report_text = message.content[0].text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anthropic API error: {str(e)}")

    return {
        "date": target_date,
        "tasks_count": len(tasks_data),
        "avg_completion": round(avg_completion, 1),
        "report": report_text,
    }
