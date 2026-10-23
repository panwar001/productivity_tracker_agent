import sqlite3
import json
import subprocess
from datetime import datetime
import streamlit as st

DB_FILE = "productivity.db"

# Page configuration
st.set_page_config(
    page_title="Work Productivity AI Agent",
    page_icon="⚡",
    layout="wide"
)

# ==========================================
# Database Functions
# ==========================================
def init_db():
    """Initialize SQLite table."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            estimated_hours REAL NOT NULL,
            actual_hours REAL DEFAULT 0.0,
            status TEXT DEFAULT 'Pending',
            percentage_done INTEGER DEFAULT 0,
            initial_notes TEXT,
            update_notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def add_task(title: str, estimated_hours: float, notes: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (date, title, estimated_hours, initial_notes) VALUES (?, ?, ?, ?)",
        (get_today_str(), title, estimated_hours, notes)
    )
    conn.commit()
    conn.close()

def fetch_tasks(date_str=None):
    if not date_str:
        date_str = get_today_str()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE date = ?", (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_task(task_id: int, percentage_done: int, status: str, actual_hours: float, update_notes: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tasks 
        SET percentage_done = ?, status = ?, actual_hours = ?, update_notes = ?
        WHERE id = ?
        """,
        (percentage_done, status, actual_hours, update_notes, task_id)
    )
    conn.commit()
    conn.close()

def run_claude_cli_report(tasks_raw) -> str:
    """Execute Claude Code CLI headlessly to produce the report."""
    formatted_tasks = []
    for t in tasks_raw:
        formatted_tasks.append({
            "id": t[0],
            "date": t[1],
            "title": t[2],
            "estimated_hours": t[3],
            "actual_hours": t[4],
            "status": t[5],
            "percentage_done": t[6],
            "initial_notes": t[7],
            "update_notes": t[8]
        })

    total_estimated = sum(t["estimated_hours"] for t in formatted_tasks)
    total_actual = sum(t["actual_hours"] for t in formatted_tasks)
    avg_completion = sum(t["percentage_done"] for t in formatted_tasks) / len(formatted_tasks)

    prompt = f"""
    You are an expert productivity coach.
    Analyze today's task execution data and generate a structured Productivity Report.

    Date: {get_today_str()}
    Overall Completion: {avg_completion:.1f}%
    Total Hours Estimated: {total_estimated}h
    Total Hours Logged: {total_actual}h

    Tasks Data:
    {json.dumps(formatted_tasks, indent=2)}

    Please analyze:
    1. **Productivity Score**: Grade (A+ to F) with reasoning.
    2. **Key Accomplishments**: What went well today.
    3. **Estimation vs Reality**: Analyze effort/time accuracy.
    4. **Blockers & Distractions**: Identify key issues based on user notes.
    5. **Actionable Suggestions for Tomorrow**: 2-3 specific improvements.
    """

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except FileNotFoundError:
        return "❌ Error: 'claude' CLI not found on PATH. Please ensure Claude Code CLI is installed."
    except subprocess.CalledProcessError as e:
        return f"❌ Error executing Claude Code CLI:\n{e.stderr}"

# ==========================================
# Streamlit Interface
# ==========================================
init_db()

st.title("⚡ Work Productivity AI Agent")
st.caption(f"Tracking tasks for **{get_today_str()}** | Powered by Claude Pro CLI")

col1, col2 = st.columns([1, 1], gap="large")

# ------------------------------------------
# Column 1: Task Entry & Update Forms
# ------------------------------------------
with col1:
    st.subheader("➕ Add New Task")
    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Task Title")
        est_hours = st.number_input("Estimated Hours", min_value=0.25, max_value=12.0, value=1.0, step=0.25)
        notes = st.text_area("Initial Notes / Context", placeholder="Optional objectives or sub-tasks...")
        submitted = st.form_submit_button("Add Task")
        
        if submitted and title:
            add_task(title, est_hours, notes)
            st.success(f"Task '{title}' added!")
            st.rerun()

    st.divider()

    st.subheader("✏️ Update Task Progress")
    today_tasks = fetch_tasks()
    
    if today_tasks:
        task_options = {f"#{t[0]} - {t[2]} ({t[6]}%)": t for t in today_tasks}
        selected_label = st.selectbox("Select Task to Update", list(task_options.keys()))
        selected_task = task_options[selected_label]

        with st.form("update_task_form"):
            pct_done = st.slider("Percentage Done", 0, 100, value=selected_task[6], step=5)
            status = st.selectbox("Status", ["Pending", "In Progress", "Completed", "Blocked"], 
                                  index=["Pending", "In Progress", "Completed", "Blocked"].index(selected_task[5]))
            actual_hrs = st.number_input("Actual Hours Logged", min_value=0.0, max_value=16.0, value=float(selected_task[4]), step=0.25)
            update_notes = st.text_area("Progress Notes / Blockers", value=selected_task[8] or "")
            
            update_submitted = st.form_submit_button("Save Update")
            if update_submitted:
                update_task(selected_task[0], pct_done, status, actual_hrs, update_notes)
                st.success("Task updated!")
                st.rerun()
    else:
        st.info("No tasks recorded for today yet.")

# ------------------------------------------
# Column 2: Dashboard & AI Report
# ------------------------------------------
with col2:
    st.subheader("📊 Today's Work Summary")
    today_tasks = fetch_tasks()

    if today_tasks:
        # Display summary metrics
        total_tasks = len(today_tasks)
        avg_pct = sum(t[6] for t in today_tasks) / total_tasks
        total_est = sum(t[3] for t in today_tasks)
        total_act = sum(t[4] for t in today_tasks)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tasks", total_tasks)
        m2.metric("Avg Progress", f"{avg_pct:.0f}%")
        m3.metric("Est. Time", f"{total_est}h")
        m4.metric("Logged Time", f"{total_act}h")

        # Visual Data Table
        st.write("---")
        for t in today_tasks:
            status_color = "🟢" if t[5] == "Completed" else ("🟡" if t[5] == "In Progress" else ("🔴" if t[5] == "Blocked" else "⚪"))
            with st.expander(f"{status_color} **{t[2]}** — {t[6]}% [{t[5]}]"):
                st.write(f"**Estimated:** {t[3]}h | **Actual:** {t[4]}h")
                if t[7]:
                    st.write(f"**Initial Note:** {t[7]}")
                if t[8]:
                    st.write(f"**Update Note:** {t[8]}")
                st.progress(t[6] / 100)

        st.divider()

        # AI Report Generator
        if st.button("🤖 Generate AI Productivity Report", type="primary", use_container_width=True):
            with st.spinner("Claude Code CLI is evaluating your day..."):
                report_md = run_claude_cli_report(today_tasks)
            st.subheader("📝 End-of-Day Report")
            st.markdown(report_md)
    else:
        st.info("Add tasks on the left panel to build today's tracking list.")
