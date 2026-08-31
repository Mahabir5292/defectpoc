from pathlib import Path
from sqlalchemy import create_engine, text
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
UPSERT = text('''INSERT INTO jira_tickets
(ticket_id,ticket_type,summary,description,root_cause,resolution,comments,application,component,priority,severity,status,environment,country,market,resolver_group,assignee,reporter,created_at,updated_at,closed_at,source_file,source_row,source_hash,raw_metadata)
VALUES (:ticket_id,:ticket_type,:summary,:description,:root_cause,:resolution,:comments,:application,:component,:priority,:severity,:status,:environment,:country,:market,:resolver_group,:assignee,:reporter,:created_at,:updated_at,:closed_at,:source_file,:source_row,:source_hash,CAST(:raw_metadata AS jsonb))
ON CONFLICT(ticket_id) DO UPDATE SET ticket_type=excluded.ticket_type,summary=excluded.summary,description=excluded.description,root_cause=excluded.root_cause,resolution=excluded.resolution,comments=excluded.comments,application=excluded.application,component=excluded.component,priority=excluded.priority,severity=excluded.severity,status=excluded.status,environment=excluded.environment,country=excluded.country,market=excluded.market,resolver_group=excluded.resolver_group,assignee=excluded.assignee,reporter=excluded.reporter,created_at=excluded.created_at,updated_at=excluded.updated_at,closed_at=excluded.closed_at,source_file=excluded.source_file,source_row=excluded.source_row,source_hash=excluded.source_hash,raw_metadata=excluded.raw_metadata,ingested_at=now() WHERE jira_tickets.source_hash IS DISTINCT FROM excluded.source_hash''')

def init_schema():
    sql = Path('/workspace/sql/001_schema.sql').read_text()
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.exec_driver_sql(statement)

def fetch_by_ids(ids):
    if not ids: return []
    with engine.begin() as conn:
        rows = conn.execute(text('SELECT * FROM jira_tickets WHERE ticket_id = ANY(:ids)'), {'ids': ids})
        found = {r._mapping['ticket_id']: dict(r._mapping) for r in rows}
    return [found[x] for x in ids if x in found]

def aggregate(filters):
    allowed = {'ticket_type','application','priority','severity','status','environment','country','market','resolver_group'}
    clauses, params = [], {}
    for k, v in filters.items():
        if k in allowed and v:
            clauses.append(f'lower({k})=lower(:{k})'); params[k] = v
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    q = text("SELECT COALESCE(root_cause,'Unknown') AS root_cause, count(*) AS count FROM jira_tickets" + where + " GROUP BY root_cause ORDER BY count DESC LIMIT 10")
    with engine.begin() as conn:
        return [dict(r._mapping) for r in conn.execute(q, params)]

def counts():
    with engine.begin() as conn:
        return [dict(r._mapping) for r in conn.execute(text('SELECT ticket_type, count(*) AS count FROM jira_tickets GROUP BY ticket_type ORDER BY ticket_type'))]
