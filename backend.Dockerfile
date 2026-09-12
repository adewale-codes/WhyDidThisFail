FROM python:3.11-slim

WORKDIR /app

# COPY paths are relative to the repo root, not this file's location --
# Railway builds with the repo root as build context by default (unlike a
# local docker-compose setup, which can point `context:` at a subfolder).
# This project's FastAPI backend already lives at repo-root `app/`, but the
# path choice here is deliberate, not incidental: get it wrong and it only
# surfaces as a build failure on Railway, not locally.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

# No CMD: railway.json's deploy.startCommand owns startup (it needs to run
# through a shell to expand Railway's $PORT -- see railway.json).
