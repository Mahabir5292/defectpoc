from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .config import settings
from .db import init_schema, counts
from .ingest import ingest_all
from .retrieval import ask
app=FastAPI(title='Enterprise Defect Triage RAG POC',version='2.0.0')
class Query(BaseModel): query:str=Field(min_length=3,max_length=4000)
@app.on_event('startup')
def startup(): init_schema()
@app.get('/health')
def health(): return {'status':'ok','llm_provider':settings.llm_provider,'embedding_provider':settings.embedding_provider}
@app.get('/stats')
def stats(): return {'tickets':counts()}
@app.post('/ingest')
def ingest():
    try:return ingest_all()
    except Exception as exc:raise HTTPException(500,str(exc))
@app.post('/query')
def query(body:Query):
    try:return ask(body.query)
    except Exception as exc:raise HTTPException(500,str(exc))
