CREATE ROLE swag LOGIN PASSWORD :'app_password';
CREATE ROLE replicator LOGIN REPLICATION PASSWORD :'replication_password';

CREATE TABLE visitors (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    ip TEXT NOT NULL,
    user_agent TEXT NOT NULL,
    browser JSONB NOT NULL DEFAULT '{}',
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL
);

CREATE TABLE clicks (
    event_id UUID PRIMARY KEY,
    visitor_id BIGINT NOT NULL REFERENCES visitors(id),
    cve_id TEXT NOT NULL,
    description TEXT,
    cvss_score DOUBLE PRECISION CHECK (cvss_score BETWEEN 0 AND 10),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX clicks_created_at_idx ON clicks (created_at DESC);
CREATE INDEX clicks_visitor_id_idx ON clicks (visitor_id);

GRANT USAGE ON SCHEMA public TO swag;
GRANT SELECT, INSERT, UPDATE, DELETE ON visitors, clicks TO swag;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO swag;
