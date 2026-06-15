from sqlalchemy import func, select

from pystack_api.db.session import session_factory
from pystack_api.models.task import Task, TaskStatus

SAMPLE_TASKS = (
    ("Sketch the first board", "Review the starter workflow.", TaskStatus.BACKLOG),
    ("Connect the generated API", "Use Hey API and TanStack Query.", TaskStatus.READY),
    (
        "Exercise database migrations",
        "Confirm both local databases migrate.",
        TaskStatus.IN_PROGRESS,
    ),
    ("Ship the smoke-test app", "Run the complete local check.", TaskStatus.REVIEW),
)


def main() -> None:
    with session_factory() as session:
        if session.scalar(select(func.count(Task.id))) != 0:
            print("Development data already exists; skipping seed.")
            return

        positions: dict[TaskStatus, int] = {}
        for title, description, status in SAMPLE_TASKS:
            position = positions.get(status, 0)
            session.add(
                Task(
                    title=title,
                    description=description,
                    status=status.value,
                    position=position,
                )
            )
            positions[status] = position + 1

        session.commit()
        print(f"Seeded {len(SAMPLE_TASKS)} tasks.")


if __name__ == "__main__":
    main()
