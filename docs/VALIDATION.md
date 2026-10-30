# Validation record — 2026-10-30

- Frontend `npm run build`: passed using Node.js 20.20.1 and a copy of the
  original installed dependencies. TypeScript and Vite both completed. Vite
  reported an existing large-bundle warning and mixed static/dynamic imports.
- Fresh offline `npm ci`: could not complete because package tarballs were not
  available in the isolated npm cache. A clean online dependency install was
  not verified; the successful build is not a reproducible-install certification.
- Python syntax parsing: all 29 Python source/test files passed. A legacy prompt
  string emits an invalid-escape warning on the host Python; parsing succeeds.
- Focused authentication tests: 5 passed (missing header, absent configuration,
  verified UID/token, rejected token and Firebase app reuse). Tests mock the
  Firebase verification call; they do not authenticate against a real project.
- Docker Compose configuration validation: passed with dummy validation values;
  containers were not started and image/plugin downloads were not exercised.
- Historical Alembic revision graph: one head (`1d1731d70e55`). No live database
  migration or schema initialization was performed.
- Source scan: no matching original environment secrets, common provider/GitHub
  key patterns, private-key headers or original personal/server paths found.
  This is a focused scan, not a comprehensive security audit.

Not run: clean Python dependency installation, live backend startup, Firebase
sign-in, model-provider calls, chat persistence, full ingestion, graph training
and real-service end-to-end tests. Those require your configured services, keys
and research data. No existing databases were changed.

Repeat focused tests after backend dependency installation:

```bash
cd backend
python -m unittest discover -s tests -v
```
