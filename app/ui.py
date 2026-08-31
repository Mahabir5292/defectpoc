import os, requests, streamlit as st
BASE=os.getenv('BACKEND_URL','http://localhost:8001')
st.set_page_config(page_title='Defect Triage RAG',layout='wide')
st.title('Enterprise Defect & Incident Triage')
with st.sidebar:
    st.caption('PostgreSQL metadata + Qdrant vectors + optional Hugging Face LLM')
    try: st.json(requests.get(BASE+'/health',timeout=10).json())
    except Exception as exc: st.warning(f'Backend not ready: {exc}')
    if st.button('Ingest configured S3 extracts',use_container_width=True):
        with st.spinner('Ingesting defects and incidents...'):
            r=requests.post(BASE+'/ingest',timeout=3600)
            if r.ok: st.json(r.json())
            else: st.error(r.text)
    if st.button('Refresh ticket counts',use_container_width=True):
        r=requests.get(BASE+'/stats',timeout=30); st.json(r.json() if r.ok else r.text)
q=st.text_area('Ask about historical defects or incidents',placeholder='Find similar P1 payment timeout incidents and recommend validation steps')
if st.button('Analyze',type='primary') and q.strip():
    with st.spinner('Retrieving evidence and preparing answer...'):
        r=requests.post(BASE+'/query',json={'query':q},timeout=600)
        if r.ok:
            x=r.json(); st.markdown(x['answer']); st.subheader('Retrieval audit'); st.json({k:x[k] for k in ['mode','filters','llm_provider','sources']})
        else: st.error(r.text)
