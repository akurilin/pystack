-- migrate:up
-- Tasks predate authentication and have no owner; per-user boards start clean.
DELETE FROM tasks;

ALTER TABLE tasks ADD COLUMN user_id text NOT NULL;

-- Board reads always filter by owner first, then order within a column, so lead
-- the index with user_id.
DROP INDEX ix_tasks_status_position;
CREATE INDEX ix_tasks_user_status_position ON tasks (user_id, status, position);

-- migrate:down
DROP INDEX ix_tasks_user_status_position;
CREATE INDEX ix_tasks_status_position ON tasks (status, position);
ALTER TABLE tasks DROP COLUMN user_id;
