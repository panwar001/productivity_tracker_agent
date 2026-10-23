import json
import os
from datetime import datetime
from anthropic import Anthropic

class ProductivityAgent:
    def __init__(self, model="claude-3-5-sonnet-20241022"):
        """Initialize the agent with the Anthropic client."""
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.tasks = []

    def add_task(self, title: str, estimated_hours: float, notes: str = ""):
        """Add a new task to the start-of-day list."""
        task = {
            "id": len(self.tasks) + 1,
            "title": title,
            "estimated_hours": estimated_hours,
            "actual_hours": 0.0,
            "status": "Pending",  # Pending, In Progress, Completed, Blocked
            "percentage_done": 0,
            "initial_notes": notes,
            "update_notes": ""
        }
        self.tasks.append(task)
        print(f"Task #{task['id']} '{title}' added ({estimated_hours}h estimated).")

    def update_task(self, task_id: int, percentage_done: int, status: str, update_notes: str, actual_hours: float = 0.0):
        """Update an existing task's progress and notes."""
        for task in self.tasks:
            if task["id"] == task_id:
                task["percentage_done"] = percentage_done
                task["status"] = status
                task["update_notes"] = update_notes
                if actual_hours > 0:
                    task["actual_hours"] = actual_hours
                print(f"Task #{task_id} updated: {percentage_done}% [{status}]")
                return
        print(f"Task #{task_id} not found.")

    def generate_end_of_day_report(self) -> str:
        """Call Claude to compute and generate the end-of-day productivity status."""
        if not self.tasks:
            return "No tasks recorded today."

        total_estimated = sum(t["estimated_hours"] for t in self.tasks)
        avg_completion = sum(t["percentage_done"] for t in self.tasks) / len(self.tasks)
        
        prompt_content = f"""
        Analyze today's task execution and generate a structured Productivity Report.

        Date: {datetime.now().strftime('%Y-%m-%d')}
        Overall Average Completion: {avg_completion:.1f}%
        Total Hours Estimated: {total_estimated}h

        Tasks Raw Data:
        {json.dumps(self.tasks, indent=2)}

        Please analyze:
        1. **Productivity Score**: (Grade from A+ to F based on completion, complexity, and overcome blockers).
        2. **Key Accomplishments**: What went well.
        3. **Time Estimation Accuracy**: How actual/estimated effort aligned.
        4. **Blockers & Notes Summary**: Highlight key hurdles or notes provided.
        5. **Actionable Recommendations for Tomorrow**: 2-3 concise tips to improve focus or estimation.
        """

        # Calling Claude SDK
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=0.3,
            system="You are an expert productivity coach and work execution analyst. Provide objective, encouraging, and highly actionable analysis based strictly on the user's task tracking data.",
            messages=[
                {"role": "user", "content": prompt_content}
            ]
        )

        return response.content[0].text


# ==========================================
# Example Usage Walkthrough
# ==========================================
if __name__ == "__main__":
    agent = ProductivityAgent()

    print("--- 🌅 START OF DAY: Plan Tasks ---")
    agent.add_task(
        title="Refactor Authentication Module",
        estimated_hours=3.0,
        notes="Focus on JWT refresh token logic"
    )
    agent.add_task(
        title="Write API Documentation",
        estimated_hours=2.0,
        notes="Cover user management endpoints"
    )
    agent.add_task(
        title="Team Standup & Planning",
        estimated_hours=1.0,
        notes="Prepare sprint updates"
    )

    print("\n--- 🌆 MID-DAY / END OF DAY: Updates ---")
    agent.update_task(
        task_id=1,
        percentage_done=100,
        status="Completed",
        actual_hours=3.5,
        update_notes="Completed. Took 30 mins longer due to edge case with token expiry."
    )
    agent.update_task(
        task_id=2,
        percentage_done=60,
        status="In Progress",
        actual_hours=1.5,
        update_notes="Drafted half the docs. Interrupted by urgent production bug fix."
    )
    agent.update_task(
        task_id=3,
        percentage_done=100,
        status="Completed",
        actual_hours=1.0,
        update_notes="Finished on time."
    )

    print("\n--- 📊 GENERATING END OF DAY PRODUCTIVITY REPORT ---")
    report = agent.generate_end_of_day_report()
    print("\n" + report)
