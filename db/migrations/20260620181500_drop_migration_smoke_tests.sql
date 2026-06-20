-- migrate:up
DROP TABLE migration_smoke_tests;

-- migrate:down
-- Restore the disposable table only if this migration is rolled back locally.
CREATE TABLE migration_smoke_tests (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamp with time zone NOT NULL DEFAULT now()
);
