-- migrate:up
CREATE TABLE tasks (
    id uuid PRIMARY KEY,
    title varchar(200) NOT NULL,
    description text NOT NULL DEFAULT '',
    status varchar(32) NOT NULL DEFAULT 'backlog',
    position integer NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT ck_tasks_position_nonnegative CHECK (position >= 0),
    CONSTRAINT ck_tasks_status CHECK (
        status IN ('backlog', 'ready', 'in_progress', 'review', 'done')
    )
);

CREATE INDEX ix_tasks_status_position ON tasks (status, position);

-- migrate:down
DROP TABLE tasks;
