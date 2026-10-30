# Quick start

1. Install Python 3.11, Node.js 20 and Docker Compose v2.
2. Copy `.env.example` to `.env` in the repository root. Set new database
   passwords and the API key for your chosen model provider.
3. Copy `frontend/.env.example` to `frontend/.env.local` and fill in the
   configuration for your own Firebase web application.
4. Place a service account from the same Firebase project at
   `secrets/firebase-service-account.json`. Enable the required Firebase
   Authentication sign-in methods and add localhost to the authorized domains.
5. Run `docker compose up -d` from the repository root and wait for the services
   to become ready.
6. Follow the README instructions to create a virtual environment and install
   backend dependencies. For an empty PostgreSQL database, run `create_tables`
   first, followed by `alembic stamp head`.
7. Start the backend from `backend/` and the frontend from `frontend/` in a
   separate terminal.
8. Load CORDIS records, PDFs and funding calls using the
   [data ingestion guide](DATA_INGESTION.md).

See [SETUP.md](SETUP.md) for complete commands and troubleshooting.

This source distribution does not include existing databases, PDF archives,
personal `.env` files or previous Git history. The original working directory
has been preserved. See [CLEANUP.md](CLEANUP.md) for the cleanup scope and
[VALIDATION.md](VALIDATION.md) for the validation status.
