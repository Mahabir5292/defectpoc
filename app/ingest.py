import io, json, uuid
import pandas as pd
from qdrant_client import QdrantClient, models
from .aws_clients import s3, embed
from .config import settings
from .db import engine, UPSERT
from .normalization import normalize, searchable_text
qdrant=QdrantClient(url=settings.qdrant_url)
def ensure_collection():
    names={c.name for c in qdrant.get_collections().collections}
    if settings.qdrant_collection not in names:
        qdrant.create_collection(settings.qdrant_collection,vectors_config=models.VectorParams(size=settings.embedding_dimensions,distance=models.Distance.COSINE))
def read_s3(key):
    if not key: raise ValueError('S3 key is blank in .env')
    body=s3.get_object(Bucket=settings.s3_bucket,Key=key)['Body'].read()
    return pd.read_csv(io.BytesIO(body)) if key.lower().endswith('.csv') else pd.read_excel(io.BytesIO(body),engine='openpyxl')
def point_id(ticket_id): return str(uuid.uuid5(uuid.NAMESPACE_URL,'jira:'+ticket_id))
def ingest_key(key,ticket_type):
    ensure_collection(); df=read_s3(key).fillna(''); stats={'seen':len(df),'upserted':0,'skipped':0,'errors':[]}
    for i,row in df.iterrows():
        try:
            ticket=normalize(row.to_dict(),ticket_type,key,int(i)+2); body=searchable_text(ticket)
            if not body: stats['skipped']+=1; continue
            vector=embed(body); db_row={**ticket,'raw_metadata':json.dumps(ticket['raw_metadata'],default=str)}
            with engine.begin() as conn: conn.execute(UPSERT,db_row)
            payload_fields = ["ticket_id","ticket_type","application","component","priority","severity","status","environment","country","market","resolver_group","created_at","summary"]

            payload = {field: ticket.get(field) for field in payload_fields}
            payload = {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in payload.items() if value is not None}
            #payload={k:ticket.get(k) for k in ['ticket_id','ticket_type','application','component','priority','severity','status','environment','country','market','resolver_group','created_at']}
            #payload={k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in payload.items() if v is not None}
            qdrant.upsert(settings.qdrant_collection,[models.PointStruct(id=point_id(ticket['ticket_id']),vector=vector,payload=payload)])
            stats['upserted']+=1
        except Exception as exc: stats['errors'].append({'row':int(i)+2,'error':str(exc)[:500]})
    return stats
def ingest_all():
    return {'defects':ingest_key(settings.defects_s3_key,'DEFECT'),'incidents':ingest_key(settings.incidents_s3_key,'INCIDENT')}
