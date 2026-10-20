# Ain Copilot in one container: FastAPI backend (port 8000, internal) + Next.js frontend (port 7860, public).
# The browser only talks to Next, which proxies /api to the backend, so the session cookie is first-party.
#
#   docker build -t ain-copilot .
#   docker run -p 7860:7860 --env-file .env ain-copilot        # then open http://localhost:7860
#
# Built for a Hugging Face Docker Space (CPU basic: 2 vCPU, 16 GB RAM, port 7860, runs as uid 1000).

# ---------------------------------------------------------------- web build
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# relative API calls + the /api rewrite to the backend inside the container
ENV NEXT_PUBLIC_API_URL="" AIN_INTERNAL_API="http://127.0.0.1:8000" NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---------------------------------------------------------------- runtime
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates libgl1 libglib2.0-0 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface EASYOCR_MODULE_PATH=/home/user/.EasyOCR
WORKDIR /home/user/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --user torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt
# bake the retrieval and OCR models into the image so the first analysis does not wait for downloads
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')" \
    && python -c "import easyocr; easyocr.Reader(['bn', 'en'], gpu=False)"

COPY --chown=user backend/ backend/
COPY --chown=user --from=web /web/.next web/.next
COPY --chown=user --from=web /web/node_modules web/node_modules
COPY --chown=user --from=web /web/package.json /web/next.config.ts web/
COPY --chown=user docker/start.sh ./start.sh

# Accounts and encrypted results live under /home/user/data (the LLM answer cache in backend/.cache). On a Space without
# persistent storage they are lost on restart (guests are temporary anyway). Set AIN_DATA_KEY as a secret, or a new
# key is made at each start and older results can no longer be read.
ENV AIN_DATA_DIR=/home/user/data AIN_RUNS_DIR=/home/user/data/runs \
    AIN_CORS="http://localhost:7860" AIN_COOKIE_SECURE=1 AIN_DENSE=1 PORT=7860
EXPOSE 7860
CMD ["bash", "start.sh"]
