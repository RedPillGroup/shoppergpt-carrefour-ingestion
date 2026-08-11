# Debian slim (not Alpine): the pipeline pulls openai / pinecone / google-cloud-storage
# / google-genai, whose wheels (incl. grpcio) are painful to build on musl. Slim gets
# manylinux wheels out of the box.
FROM python:3.11-slim

ENV POETRY_VERSION=1.8.5 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir "poetry==$POETRY_VERSION" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --only main

COPY run.py ./
COPY ingest/ ./ingest/

# Static store-concepts CSV — NOT part of the GCS export, so it can't be fetched
# at runtime; it must ship in the image. Read by the --stores step (see README
# "Store concepts"). JSON-array COPY form because the filename has spaces.
COPY ["data/Evénement X Concept - Concept X Magasin.csv", "./data/Evénement X Concept - Concept X Magasin.csv"]

# Daily job: pull the latest exports from GCS, then run the full ingestion
# (stores → prices → products → catalogue → pinecone).
CMD ["poetry", "run", "python", "run.py", "--fetch"]
