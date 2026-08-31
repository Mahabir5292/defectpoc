#!/usr/bin/env bash
set -euo pipefail
if [ ! -f .env ]; then cp .env.example .env; echo 'Created .env. Update it, then rerun ./deploy.sh'; exit 1; fi
docker compose config >/dev/null
docker compose up --build -d
echo 'Containers started. Check: docker compose ps'
echo 'Logs: docker compose logs -f backend'
echo 'UI: http://YOUR_EC2_PUBLIC_IP:8501'
