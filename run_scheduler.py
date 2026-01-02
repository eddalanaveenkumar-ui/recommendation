from app.scheduler import build_tasks

tasks = build_tasks()
print(f"Total tasks generated: {len(tasks)}")