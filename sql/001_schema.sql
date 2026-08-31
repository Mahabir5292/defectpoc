CREATE TABLE IF NOT EXISTS jira_tickets (
  ticket_id text PRIMARY KEY,
  ticket_type text NOT NULL CHECK (ticket_type IN ('DEFECT','INCIDENT')),
  summary text, description text, root_cause text, resolution text, comments text,
  application text, component text, priority text, severity text, status text,
  environment text, country text, market text, resolver_group text,
  assignee text, reporter text,
  created_at timestamptz, updated_at timestamptz, closed_at timestamptz,
  source_file text NOT NULL, source_row integer NOT NULL, source_hash text NOT NULL,
  raw_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  ingested_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ticket_filters ON jira_tickets(ticket_type, application, priority, severity, status);
CREATE INDEX IF NOT EXISTS ix_ticket_dates ON jira_tickets(created_at, closed_at);
CREATE INDEX IF NOT EXISTS ix_ticket_raw_metadata ON jira_tickets USING gin(raw_metadata);
CREATE TABLE IF NOT EXISTS ingestion_runs (
  run_id uuid PRIMARY KEY, source_file text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
  status text NOT NULL, rows_seen integer NOT NULL DEFAULT 0,
  rows_upserted integer NOT NULL DEFAULT 0, rows_skipped integer NOT NULL DEFAULT 0,
  error_message text
);
