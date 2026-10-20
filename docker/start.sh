#!/usr/bin/env bash
# Container entrypoint: FastAPI on 127.0.0.1:8000 (not exposed), Next.js on 0.0.0.0:$PORT proxying /api to it.
set -euo pipefail

# On a Hugging Face Space the public origin is https://$SPACE_HOST; the backend's CSRF check must accept it.
if [[ -n "${SPACE_HOST:-}" && "${AIN_CORS}" == "http://localhost:7860" ]]; then
  export AIN_CORS="https://${SPACE_HOST}"
fi
mkdir -p "${AIN_DATA_DIR}" "${AIN_RUNS_DIR}"

cd /home/user/app/backend
python -m uvicorn ain.api:app --host 127.0.0.1 --port 8000 --proxy-headers &
API_PID=$!

# wait for the backend (it loads the corpus and the retrieval model first)
for _ in $(seq 1 120); do
  if curl -fs http://127.0.0.1:8000/api/health > /dev/null; then break; fi
  if ! kill -0 "$API_PID" 2> /dev/null; then echo "backend failed to start" >&2; exit 1; fi
  sleep 1
done

cd /home/user/app/web
exec node_modules/.bin/next start -H 0.0.0.0 -p "${PORT:-7860}"
