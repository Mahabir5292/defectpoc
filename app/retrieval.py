import re
from qdrant_client import QdrantClient, models
from .aws_clients import embed
from .llm import generate
from .config import settings
from .db import fetch_by_ids, aggregate
qdrant=QdrantClient(url=settings.qdrant_url)
def route(query):
    return 'sql' if any(x in query.lower() for x in ['how many','count','most common','top root cause']) else 'hybrid'
def parse_filters(query):
    filters={}
    for p in ['p1','p2','p3','p4']:
        if re.search(rf'\b{p}\b',query,re.I): filters['priority']=p.upper()
    if re.search(r'\bdefects?\b',query,re.I): filters['ticket_type']='DEFECT'
    if re.search(r'\bincidents?\b',query,re.I): filters['ticket_type']='INCIDENT'
    return filters
def qfilter(filters):
    must=[models.FieldCondition(key=k,match=models.MatchValue(value=v)) for k,v in filters.items()]
    return models.Filter(must=must) if must else None
def vector_search(query,filters):
    result=qdrant.query_points(collection_name=settings.qdrant_collection,query=embed(query),query_filter=qfilter(filters),limit=settings.top_k,score_threshold=settings.min_score,with_payload=True).points
    return [{'ticket_id':h.payload.get('ticket_id'),'score':round(h.score,4)} for h in result]
def build_context(records,scores):
    score_map={x['ticket_id']:x['score'] for x in scores}; blocks=[]
    for r in records:
        vals={k:r.get(k) for k in ['ticket_id','ticket_type','summary','description','root_cause','resolution','application','component','priority','severity','status','environment','country','market','resolver_group']}
        vals['similarity_score']=score_map.get(r['ticket_id']); blocks.append('\n'.join(f'{k}: {v}' for k,v in vals.items() if v is not None))
    return '\n\n---\n\n'.join(blocks)[:settings.max_context_chars]
def retrieval_only(records,hits):
    if not records: return 'No matching evidence was found above the configured similarity threshold.'
    lines=['LLM is disabled. Retrieved evidence:']
    score_map={h['ticket_id']:h['score'] for h in hits}
    for r in records:
        lines.append(f"- {r['ticket_id']} | score {score_map.get(r['ticket_id'])} | {r.get('summary') or 'No summary'} | RCA: {r.get('root_cause') or 'Not recorded'} | Resolution: {r.get('resolution') or 'Not recorded'}")
    return '\n'.join(lines)
def ask(query):
    filters=parse_filters(query); mode=route(query)
    if mode=='sql':
        rows=aggregate(filters); context='Structured database result:\n'+str(rows); sources=[]; records=[]
    else:
        hits=vector_search(query,filters)[:settings.final_k]; records=fetch_by_ids([h['ticket_id'] for h in hits]); context=build_context(records,hits); sources=hits
    if settings.llm_provider.lower()=='none':
        answer=str(rows) if mode=='sql' else retrieval_only(records,sources)
    else:
        system='You are an enterprise defect-triage assistant. Use only supplied evidence. Never invent ticket IDs, root causes, fixes, counts, or confidence. Cite ticket IDs inline. State when evidence is insufficient. Recommendations require human validation.'
        prompt=f'User query:\n{query}\n\nEvidence:\n{context}\n\nGive a direct answer, supporting tickets or data, probable pattern, recommended validation steps, and limitations.'
        answer=generate(system,prompt)
    return {'mode':mode,'filters':filters,'llm_provider':settings.llm_provider,'answer':answer,'sources':sources}
