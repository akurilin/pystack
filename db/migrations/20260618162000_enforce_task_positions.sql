-- migrate:up
DROP INDEX ix_tasks_user_status_position;

ALTER TABLE tasks
    ADD CONSTRAINT uq_tasks_user_status_position
    UNIQUE (user_id, status, position)
    DEFERRABLE INITIALLY DEFERRED;

-- migrate:down
ALTER TABLE tasks DROP CONSTRAINT uq_tasks_user_status_position;

CREATE INDEX ix_tasks_user_status_position ON tasks (user_id, status, position);
