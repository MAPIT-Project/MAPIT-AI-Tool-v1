# MAPIT AI Tool v1

MAPIT AI Domain Expert Tool helps explore European research projects, funding calls,
publications and partner organizations through AI-assisted chat, document search,
knowledge graphs and visualizations.

The application combines a React/TypeScript frontend with a FastAPI backend.
PostgreSQL stores chat history and preferences; Neo4j stores research relationships;
Qdrant provides vector retrieval; Elasticsearch provides text search. Firebase
Authentication identifies users. Model integrations include OpenAI, Ollama,
Mistral and Gemini; availability depends on the configured provider and model.

## Local installation

See the [quick start](docs/QUICK_START.md) and [detailed setup](docs/SETUP.md).
The intended baseline is Python 3.11, Node.js 20 and Docker Compose v2.
A working installation requires your own Firebase project, service account and
model credentials. Research datasets and database contents are **not bundled**.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
# Fill in both files and place the Firebase service account under secrets/.
docker compose up -d
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
python -c 'from app.database import create_tables; create_tables()'
alembic stamp head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open http://localhost:5173; API documentation is at http://localhost:8000/docs.
An empty research database produces empty search results. Follow the
[data ingestion guide](docs/DATA_INGESTION.md) to populate it.

## Repository layout

| Directory | Contents |
| --- | --- |
| `backend/app/` | FastAPI endpoints, retrieval, chat persistence and authentication |
| `backend/migrations/` | Historical PostgreSQL migrations |
| `frontend/src/` | React UI, authentication, graphs and maps |
| `scripts/` | CORDIS/call ingestion and optional graph-processing tools |
| `test_scripts/` | Retained operational author extraction and embedding utilities |
| `docs/` | Installation, ingestion, cleanup and publication instructions |

## Validation and limitations

See [validation results](docs/VALIDATION.md). This is a cleaned source release,
not a claim of a fully tested production deployment. Full chat, Firebase login,
provider calls and ingestion need configured services and datasets.
The dependency versions originate from the existing application and require a
separate dependency/security upgrade review before an internet-facing deployment.

## Publishing and contribution

[GitHub publication commands](docs/PUBLISH_GITHUB.md) target the public repository
`MAPIT-Project/MAPIT-AI-Tool-v1`. The original Git history, secrets, generated data
and local development artifacts are excluded; see [cleanup notes](docs/CLEANUP.md).

No project license was supplied during preparation. Public visibility alone does
not grant an open-source license; the project owner should choose a license.
