import hashlib, json, re
import pandas as pd
ALIASES = {
 'ticket_id':['ticket_id','key','issue key','issue_key','def_id','defect id','incident id','number','id'],
 'summary':['summary','short description','title','defect summary'], 'description':['description','issue description','details'],
 'root_cause':['root cause','root_cause','rca','cause'], 'resolution':['resolution','fix','solution','workaround'],
 'comments':['comments','comment','work notes','work_notes'], 'application':['application','application name','business service','service'],
 'component':['component','module','affected module'], 'priority':['priority'], 'severity':['severity'], 'status':['status','state'],
 'environment':['environment','env'], 'country':['country'], 'market':['market'],
 'resolver_group':['resolver group','assignment group','support group'], 'assignee':['assignee','assigned to'], 'reporter':['reporter','opened by'],
 'created_at':['created','created date','created_at'], 'updated_at':['updated','updated date','updated_at'], 'closed_at':['closed','closed date','resolved date','closed_at']}
def key(s): return re.sub(r'[^a-z0-9]+',' ',str(s).strip().lower()).strip()
def first(row,names):
    normalized={key(k):v for k,v in row.items()}
    for name in names:
        v=normalized.get(key(name))
        if v is not None and str(v).strip() and str(v).lower()!='nan': return v
    return None
def normalize(row,ticket_type,source_file,source_row):
    out={field:first(row,names) for field,names in ALIASES.items()}
    if not out['ticket_id']: raise ValueError('No ticket ID found. Add a Jira key/ID column or extend ALIASES.')
    out['ticket_id']=str(out['ticket_id']).strip(); out['ticket_type']=ticket_type
    out['source_file']=source_file; out['source_row']=source_row
    for f in ('created_at','updated_at','closed_at'):
        out[f]=pd.to_datetime(out[f],errors='coerce',utc=True); out[f]=None if pd.isna(out[f]) else out[f].to_pydatetime()
    raw={str(k):None if pd.isna(v) else v for k,v in row.items()}
    out['raw_metadata']=raw; out['source_hash']=hashlib.sha256(json.dumps(raw,sort_keys=True,default=str).encode()).hexdigest()
    return out
def searchable_text(t):
    fields=[('Ticket ID',t.get('ticket_id')),('Ticket type',t.get('ticket_type')),('Summary',t.get('summary')),('Description',t.get('description')),('Root cause',t.get('root_cause')),('Resolution',t.get('resolution')),('Comments',t.get('comments')),('Application',t.get('application')),('Component',t.get('component'))]
    return '\n'.join(f'{k}: {v}' for k,v in fields if v and str(v).strip())
