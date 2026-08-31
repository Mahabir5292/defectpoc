# Copy-paste deployment guide

## 1. EC2 prerequisites
Use an EC2 Linux host with Docker and the Docker Compose plugin installed. Attach an IAM role that can read the two configured S3 objects and invoke the configured Titan embedding model. Do not put AWS access keys in `.env`.

Security group for the POC:
- TCP 22 from your IP, if using SSH.
- TCP 8501 from your IP or approved demo users.
- TCP 8000 only if you want direct API testing. Qdrant and PostgreSQL are not published by this compose file.

## 2. Upload and unzip
```bash
unzip enterprise-defect-triage-rag-poc.zip
cd enterprise-defect-triage-rag-poc
cp .env.example .env
nano .env
```

## 3. Minimum `.env` changes
Update these values:
```dotenv
AWS_REGION=ap-south-1
S3_BUCKET=your-real-bucket
DEFECTS_S3_KEY=jira-uploads/defects.xlsx
INCIDENTS_S3_KEY=jira-uploads/incidents.xlsx
POSTGRES_PASSWORD=choose-a-poc-password
DATABASE_URL=postgresql+psycopg://triage:choose-a-poc-password@postgres:5432/triage
```
The password in `POSTGRES_PASSWORD` and `DATABASE_URL` must match. URL-encode special characters in `DATABASE_URL`; for the quickest POC, use letters and numbers.

Keep the existing Titan settings unless you deliberately change the embedding model:
```dotenv
EMBEDDING_PROVIDER=bedrock
EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSIONS=1024
QDRANT_COLLECTION=jira_tickets_titan_v2
```
If the embedding model or dimension changes, use a new collection name and re-ingest.

## 4. LLM choice
### Recommended first validation, retrieval only
```dotenv
LLM_PROVIDER=none
```
This avoids the model download and proves S3, PostgreSQL, Titan, Qdrant, API, and UI first.

### Lightweight local Hugging Face LLM
```dotenv
LLM_PROVIDER=huggingface
HF_MODEL_ID=Qwen/Qwen2.5-0.5B-Instruct
HF_DEVICE=cpu
HF_MAX_NEW_TOKENS=350
HF_TEMPERATURE=0.1
HF_CACHE_DIR=/models/huggingface
```
The model downloads on first use and is persisted in the `hf_cache` Docker volume. CPU inference is suitable for a demo but slower than a hosted model.

### Bedrock chat model later
```dotenv
LLM_PROVIDER=bedrock
LLM_MODEL_ID=your-enabled-bedrock-chat-model-id
```

## 5. Start
```bash
chmod +x deploy.sh
./deploy.sh
docker compose ps
curl http://localhost:8000/health
```

## 6. Open and ingest
Open `http://YOUR_EC2_PUBLIC_IP:8501`. Click **Ingest configured S3 extracts** once. Review row errors in the JSON response. Then click **Refresh ticket counts**.

## 7. Test queries
```text
Find incidents similar to authentication service unavailable
Find P1 defects related to login timeout
What are the most common root causes across incidents?
Recommend validation steps for a payment timeout using only the retrieved history
```

## 8. Switch on Hugging Face after baseline works
```bash
nano .env
# set LLM_PROVIDER=huggingface
docker compose up -d --force-recreate backend ui
docker compose logs -f backend
```
The first LLM query triggers the model download. Keep enough disk space for the Docker image and model cache.

## 9. Validation commands
```bash
docker compose ps
docker compose logs --tail=200 backend
docker compose exec postgres psql -U triage -d triage -c "select ticket_type,count(*) from jira_tickets group by ticket_type;"
curl http://localhost:8000/stats
```

## 10. Common fixes
- `AccessDenied` from S3: correct the EC2 role and exact bucket/object permissions.
- Bedrock model error: verify Titan model access in the configured region and IAM `bedrock:InvokeModel`.
- `NoSuchKey`: compare the exact S3 object key with `.env`.
- PostgreSQL authentication error: ensure `POSTGRES_PASSWORD` matches the password inside `DATABASE_URL`. If you previously created the volume with another password and have no data to preserve, run `docker compose down -v` and start again. This deletes local PostgreSQL and Qdrant data.
- Qdrant dimension mismatch: change `QDRANT_COLLECTION` to a new name and re-ingest.
- Hugging Face is too slow or memory constrained: set `LLM_PROVIDER=none` for the demo, or use a larger EC2 instance.

## 11. Stop and preserve data
```bash
docker compose down
```
Do not add `-v` unless you intentionally want to delete PostgreSQL, Qdrant, and the Hugging Face cache.
