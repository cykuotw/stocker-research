CREATE SCHEMA IF NOT EXISTS runtime;
CREATE SCHEMA IF NOT EXISTS checkpoints;
CREATE TABLE IF NOT EXISTS runtime.schema_migrations (
    version integer PRIMARY KEY,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS runtime.assistants (
    assistant_id uuid PRIMARY KEY,
    graph_id text NOT NULL,
    name text NOT NULL,
    config jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS runtime.sessions (
    session_id uuid PRIMARY KEY,
    assistant_id uuid NOT NULL REFERENCES runtime.assistants,
    graph_id text NOT NULL,
    config jsonb NOT NULL,
    title text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS runtime.runs (
    run_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES runtime.sessions,
    action text NOT NULL CHECK (action IN ('input', 'resume', 'recover')),
    request jsonb NOT NULL,
    idempotency_key text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'running', 'interrupted', 'completed', 'failed', 'cancelled', 'recovery_required')),
    error jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (session_id, idempotency_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run_per_session
ON runtime.runs (session_id) WHERE status IN ('pending', 'running');
CREATE INDEX IF NOT EXISTS runs_by_session ON runtime.runs (session_id, created_at, run_id);
CREATE INDEX IF NOT EXISTS pending_runs ON runtime.runs (created_at, run_id) WHERE status = 'pending';
CREATE TABLE IF NOT EXISTS runtime.events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES runtime.sessions,
    run_id uuid NOT NULL REFERENCES runtime.runs,
    kind text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_by_run ON runtime.events (run_id, event_id);
CREATE INDEX IF NOT EXISTS events_by_session ON runtime.events (session_id, event_id);
