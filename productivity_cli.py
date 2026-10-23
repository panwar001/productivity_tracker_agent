import sqlite3
import json
import subprocess
from datetime import datetime

DB_FILE = "productivity.db"


# ==========================================
# Database Helper Setup
# ==========================================
def init_db():
    """Create the SQLite database and tasks table if they don't exist."""
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


# ==========================================
# Productivity Agent Class
# ==========================================
class ProductivityAgent:
    def __init__(self):
        """No API key or SDK client needed—uses local Claude Code CLI auth."""
        pass

    def get_today_str(self):
        return datetime.now().strftime("%Y-%m-%d")

    def add_task(self, title: str, estimated_hours: float, notes: str):
        """Insert a new task into SQLite."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (date, title, estimated_hours, initial_notes)
            VALUES (?, ?, ?, ?)
            """,
            (self.get_today_str(), title, estimated_hours, notes)
        )
        conn.commit()
        conn.close()
        print(f"\n✅ Task '{title}' added successfully!")

    def view_tasks(self, date_str=None):
        """Fetch tasks for a given date (defaults to today)."""
        if not date_str:
            date_str = self.get_today_str()

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE date = ?", (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def update_task(self, task_id: int, percentage_done: int, status: str, actual_hours: float, update_notes: str):
        """Update an existing task in SQLite."""
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
        updated_rows = cursor.rowcount
        conn.close()

        if updated_rows > 0:
            print(f"\n✅ Task #{task_id} updated successfully!")
        else:
            print(f"\n❌ Task #{task_id} not found.")

    def generate_end_of_day_report(self) -> str:
        """Fetch today's tasks and request an AI productivity report using Claude Code CLI."""
        today = self.get_today_str()
        tasks_raw = self.view_tasks(today)

        if not tasks_raw:
            return "No tasks found for today. Add some tasks first!"

        # Format DB rows into a readable structure for Claude
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

        Date: {today}
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

        print("\n⏳ Calling Claude Code CLI (using your Claude Pro account)...")

        try:
            # Executes the prompt headlessly via your authenticated Claude Pro CLI session
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except FileNotFoundError:
            return "❌ Error: 'claude' CLI not found on PATH. Install it and run 'claude auth login'."
        except subprocess.CalledProcessError as e:
            return f"❌ Error executing Claude Code CLI:\n{e.stderr}"


# ==========================================
# CLI Interactive Loop
# ==========================================
def print_tasks_table(tasks):
    """Pretty prints task rows in terminal."""
    if not tasks:
        print("\nNo tasks found.")
        return

    print("\n" + "=" * 85)
    print(f"{'ID':<4} | {'Title':<25} | {'Est(h)':<6} | {'Act(h)':<6} | {'Progress':<8} | {'Status':<12}")
    print("=" * 85)
    for t in tasks:
        # t[0]=id, t[2]=title, t[3]=est, t[4]=act, t[6]=pct, t[5]=status
        print(f"{t[0]:<4} | {t[2][:25]:<25} | {t[3]:<6.1f} | {t[4]:<6.1f} | {t[6]:<7}% | {t[5]:<12}")
    print("=" * 85)


def main():
    init_db()
    agent = ProductivityAgent()

    while True:
        print("\n--- 🚀 WORK PRODUCTIVITY AGENT ---")
        print("1. Add New Task (Start of Day / Plan)")
        print("2. View Today's Tasks")
        print("3. Update Task Progress")
        print("4. Generate End-of-Day Productivity Report")
        print("5. Exit")

        choice = input("\nSelect an option (1-5): ").strip()

        if choice == "1":
            title = input("Enter task title: ").strip()
            est_str = input("Enter estimated hours (e.g., 1.5): ").strip()
            notes = input("Enter initial notes/context (optional): ").strip()

            try:
                est_hours = float(est_str)
                agent.add_task(title, est_hours, notes)
            except ValueError:
                print("❌ Invalid input for estimated hours. Task creation canceled.")

        elif choice == "2":
            tasks = agent.view_tasks()
            print_tasks_table(tasks)

        elif choice == "3":
            tasks = agent.view_tasks()
            if not tasks:
                print("\nNo tasks available to update. Add a task first.")
                continue

            print_tasks_table(tasks)
            task_id_str = input("\nEnter Task ID to update: ").strip()

            try:
                task_id = int(task_id_str)
                pct_str = input("Enter percentage done (0-100): ").strip()
                pct = int(pct_str)

                print("\nStatus options: 1. Pending  2. In Progress  3. Completed  4. Blocked")
                status_choice = input("Select status option (1-4): ").strip()
                status_map = {"1": "Pending", "2": "In Progress", "3": "Completed", "4": "Blocked"}
                status = status_map.get(status_choice, "In Progress")

                act_str = input("Enter actual hours spent today: ").strip()
                actual_hours = float(act_str) if act_str else 0.0

                update_notes = input("Enter update notes / blocker details: ").strip()

                agent.update_task(task_id, pct, status, actual_hours, update_notes)

            except ValueError:
                print("❌ Invalid input. Update canceled.")

        elif choice == "4":
            report = agent.generate_end_of_day_report()
            print("\n" + "=" * 40 + " PRODUCTIVITY REPORT " + "=" * 40)
            print(report)
            print("=" * 101)

        elif choice == "5":
            print("\nGoodbye! Have a productive day.")
            break
        else:
            print("❌ Invalid choice. Please pick between 1 and 5.")


if __name__ == "__main__":
    main()