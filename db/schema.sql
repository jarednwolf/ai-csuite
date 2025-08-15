
-- Phase 1: create extensions only (no tables yet).
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Phase 11 visibility (DDL is created via SQLAlchemy; provided here for reference only)
--
-- CREATE TABLE graph_states (
--   id UUID PRIMARY KEY,
--   run_id UUID NOT NULL,
--   step_index INTEGER NOT NULL,
--   step_name VARCHAR(64) NOT NULL,
--   status VARCHAR(16) NOT NULL,
--   attempt INTEGER NOT NULL DEFAULT 1,
--   state_json JSONB NOT NULL,
--   logs_json JSONB,
--   error TEXT,
--   created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
--   updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
-- );
-- CREATE UNIQUE INDEX uq_graph_state_run_step_attempt ON graph_states(run_id, step_index, attempt);
-- CREATE INDEX ix_graph_state_run ON graph_states(run_id);

