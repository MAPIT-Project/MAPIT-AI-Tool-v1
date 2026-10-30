# Source cleanup record

The fresh repository was prepared from the supplied MAPIT-AI working directory.
The original directory was not edited. No previous Git history was copied.

## Included

- Backend application modules, prompts and schema metadata, historical migrations.
- Frontend source, assets, public resources, package lock and build configuration.
- Call scraping and ingestion, CORDIS/PDF ingestion, author extraction and embedding
  utilities, plus one retained graph training implementation and community labeling.
- New README, English installation notes, environment examples, local Compose
  services, ingestion guide, publication commands and focused authentication tests.

## Excluded (remain in the original directory)

- `.git`, all real `.env` files and credentials.
- `node_modules`, frontend build outputs, Python caches and local environments.
- Database backups, research datasets, downloaded PDFs/HTML, model weights,
  checkpoints, logs, debug contexts and generated visualizations.
- Root-level one-off debug/demo/test scripts, backend standalone diagnostic scripts,
  frontend test pages, historical fix summaries and duplicate experimental trainers.
- Personal installation notes, which contained credentials; relevant procedures
  were rewritten without their sensitive values.

Unreferenced prototype-looking UI files were retained when removal could change
behavior. This is a curated source export, not a broad application rewrite.

## Intentional code changes

- Removed a hard-coded provider API key; credentials now come from the environment.
- Load the root environment before importing backend database/routes.
- Use a SQLAlchemy URL object so PostgreSQL passwords containing reserved
  characters are handled correctly; remove the default database password.
- Share one Firebase authentication dependency and fail closed when credentials
  are absent; reuse the initialized Admin app. Send the unmodified Firebase token
  from the UI. Legacy mock-user chat ownership is not migrated.
- Configure CORS origins through the environment and remove the old server address.
- Resolve local document paths relative to the checkout or `DATA_ROOT`, with HTML escaping.
- Read Neo4j credentials from the environment in retained graph tools.
- Align core ingestion dependencies with the backend and constrain transformers/tokenizers
  for the legacy sentence-transformers version; keep graph extras separate.

## Before publication

Rotate the provider key found in the old source and any credentials previously
shared or committed. They are not reproduced here. Choose a project license and
confirm rights to included branding/assets. Dependency modernization, full security
review and real-service acceptance testing are separate work from this cleanup.
