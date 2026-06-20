-- migrate:up
-- Disposable table for verifying that automated production migrations run.
CREATE TABLE migration_smoke_tests (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamp with time zone NOT NULL DEFAULT now()
);

-- migrate:down
DROP TABLE migration_smoke_tests;
