# Installation

## 1. Prerequisites and configuration

Use Python 3.11, Node.js 20 (see `.nvmrc`), npm and Docker Compose v2.
Allow memory for four database services plus Torch/embedding models. The first
start downloads transformer models and Neo4j plugins and therefore needs internet.
These Docker image tags are a development baseline, not a tested production matrix.

From the repository root, copy `.env.example` to `.env` and
`frontend/.env.example` to `frontend/.env.local`. Set new PostgreSQL and Neo4j
passwords. Backend and ingestion tools discover the root `.env`; the frontend
uses its own Vite environment file. Existing shell environment values take priority.
For the provided Compose file keep PostgreSQL's port at 5432 and Neo4j's user as
`neo4j`. Blank Elasticsearch/Qdrant credentials match the local-only services.
For external servers supply their actual URLs and authentication values instead.

Create/configure a Firebase project with Email/Password and Google sign-in as
needed by the UI. Add localhost to Authentication authorized domains. Copy the web
app configuration to the frontend environment file. Download a service-account
JSON into `secrets/firebase-service-account.json`; the backend path is relative to
the repository root. Web config and service account must belong to the same project.
Never place a service account or provider secret in a `VITE_` variable.

Set `OPENAI_API_KEY` for the default chat model and topic-expansion/partner features.
Other providers are optional; configure their key or the Ollama URL before choosing
them. Model names and access depend on your provider account.

## 2. Start the databases

```bash
docker compose up -d
docker compose ps
docker compose logs --tail=80 neo4j
```

Wait for service initialization. Neo4j Browser is at http://localhost:7474.
Qdrant uses 6333, Elasticsearch 9200 and PostgreSQL 5432.
If you already run services on these ports, use your existing services with the
correct environment settings or stop those services before starting Compose.
Compose creates new named volumes and does not import existing databases.
`docker compose down` stops services while preserving these volumes.

## 3. Backend and fresh PostgreSQL schema

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
python -c 'from app.database import create_tables; create_tables()'
alembic stamp head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The schema command uses the current SQLAlchemy models, including token counts and
Lucene queries. **For a new empty database only**, `stamp head` records this current
schema as the historical migration head. Do not run `alembic upgrade head` on an
empty database: the earliest legacy migration assumes tables already exist.
Do not stamp an old database without first reconciling its actual schema.
`create_tables` does not update columns in existing tables. Existing databases
need a separate reviewed migration; this source release starts with fresh data.

Run the backend from `backend/` because visualization output paths are relative.
The model can take time to download/load. Missing Firebase credentials yield 503
on authenticated endpoints; invalid tokens yield 401. There is no mock-user fallback.
Changing from legacy mock IDs to Firebase UIDs does not migrate old chat ownership.

## 4. Frontend

In another terminal, from the root:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open http://localhost:5173. For a build, run `npm run build`.
Vite embeds frontend environment values at build time; rebuild after changing them.
If the UI runs on another origin, update `CORS_ORIGINS` and Firebase authorized domains.

## 5. Populate research data and verify

Follow [DATA_INGESTION.md](DATA_INGESTION.md). Verify Firebase login, a chat round
trip, persisted history, a project search and partner/graph features with your data.
API docs alone do not demonstrate end-to-end readiness.

## Deployment considerations

Compose is for local development: Qdrant and Elasticsearch are unauthenticated but
bound to localhost. Use authenticated private services, HTTPS and explicit origins
for deployment. Generated visualization files are currently served as static files;
review access control before storing private information. Legacy document `file://`
links refer to the server filesystem and may be blocked by browsers; remote document
serving needs its own access-controlled implementation. Debug/context logging is
inherited from the source and may contain user text. Review it before public hosting.
