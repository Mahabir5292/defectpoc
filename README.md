# Enterprise Defect Triage RAG, 1-day POC

This package preserves the original S3, Titan embedding, Qdrant, FastAPI, and Streamlit flow and adds PostgreSQL as the full metadata system of record plus an optional local lightweight Hugging Face LLM.

## Data flow
1. Defect and incident Excel/CSV extracts are read from S3.
2. Every complete normalized Jira row is upserted into PostgreSQL.
3. Searchable narrative fields are embedded with Amazon Titan Text Embeddings V2.
4. Vectors and minimal filter metadata are upserted into Qdrant using deterministic IDs.
5. A query uses PostgreSQL for simple counts or Qdrant for semantic matches, then fetches full records from PostgreSQL.
6. `LLM_PROVIDER=huggingface` generates a grounded answer locally. Set `none` for retrieval-only or `bedrock` for Bedrock Converse.

## Fastest start
```bash
cp .env.example .env
nano .env
chmod +x deploy.sh
./deploy.sh
```
Open `http://YOUR_EC2_PUBLIC_IP:8501`, click **Ingest configured S3 extracts**, then query.

Read `DEPLOYMENT_GUIDE.md` before deployment. For a small 1-day POC, start with `LLM_PROVIDER=none` to validate ingestion, PostgreSQL, and Qdrant. Then change to `huggingface` and restart the backend and UI.
