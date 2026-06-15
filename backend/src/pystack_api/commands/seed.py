import psycopg

from pystack_api.core.config import get_settings
from pystack_api.schemas.task import TaskStatus
from pystack_api.services import tasks as task_service

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
    with psycopg.connect(get_settings().database_url) as connection:
        if task_service.count_tasks(connection) != 0:
            print("Development data already exists; skipping seed.")
            return

        positions: dict[TaskStatus, int] = {}
        for title, description, status in SAMPLE_TASKS:
            position = positions.get(status, 0)
            task_service.create_task_at_position(
                connection,
                title=title,
                description=description,
                status=status.value,
                position=position,
            )
            positions[status] = position + 1

        print(f"Seeded {len(SAMPLE_TASKS)} tasks.")


if __name__ == "__main__":
    main()
