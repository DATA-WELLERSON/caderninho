# AGENTS.md

Guidance for AI coding agents working in this repository.

Caderninho do Fiado: a deliberately tiny FastAPI app (bar tab tracker). The point of the project is the
production path around it — tests, managed Postgres (Supabase), versioned migrations, Vercel deploy,
Sentry, CI/CD — so changes to infra/CI are as important as app code. Code, comments and user-facing
text are in Portuguese; keep it that way.

## Commands

Uses `uv` (Python 3.12). Local Postgres comes from `docker-compose.yml` on port **5433**.

```bash
uv sync                                   # install everything (incl. dev group)
docker compose up -d --wait               # local Postgres
uv run python -m app.migrate              # apply migrations to DATABASE_URL
uv run uvicorn app.main:app --reload      # http://localhost:8000 (/docs for Swagger)

uv run ruff check . && uv run ruff format --check .
uv run pytest                                            # in-memory only, no DB needed
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/caderninho uv run pytest
uv run pytest tests/test_api.py::test_pagar              # single test
uv run pytest "tests/test_repository.py::test_ranking[postgres]"   # one contract-test variant
```

pytest always runs with coverage (`addopts` in `pyproject.toml`).

## Architecture

- `app/main.py` — all routes. Routes depend only on the `FiadoRepository` Protocol via `Depends(get_repo)`;
  domain errors (`FiadoNaoEncontradoError`, `FiadoJaPagoError`) are mapped to 404/409 here.
- `app/repository.py` — the Protocol plus two implementations: `InMemoryFiadoRepository` and
  `PostgresFiadoRepository` (raw SQL with psycopg, no ORM). Any behavior change must be made in **both**.
- Tests are split accordingly:
  - `tests/test_api.py` uses the in-memory repo via `app.dependency_overrides` (see `tests/conftest.py`).
  - `tests/test_repository.py` is a **contract test** parametrized over both implementations; the
    Postgres variant is skipped unless `TEST_DATABASE_URL` is set. It truncates tables, which is why it
    uses `TEST_DATABASE_URL` and never `DATABASE_URL`.
- `app/migrate.py` — home-grown migrator: applies `migrations/NNN_*.sql` in order inside a transaction,
  tracked in `schema_migrations`. Add schema changes as a new numbered file; never edit applied ones.
  CI runs migrations against Supabase **before** deploying.
- `app/config.py` — pydantic-settings; reads `.env`. `environment`/`release` fall back to Vercel's
  `VERCEL_ENV` / `VERCEL_GIT_COMMIT_SHA`.

## Constraints that aren't obvious

- **Serverless + Supabase pooler**: one connection per repository call, with `prepare_threshold=None`
  (transaction-mode pooler on port 6543 doesn't support prepared statements). Don't add a connection pool.
- **Vercel entrypoint** is `api/index.py`, which re-exports `app`; `vercel.json` rewrites every path to it
  and disables Vercel's git auto-deploy — deploys happen only from GitHub Actions after lint + tests.
- **`requirements.txt` is generated** from `uv.lock` (Vercel installs from it). Never edit by hand; after
  changing deps run
  `uv export --no-dev --no-hashes --no-header --no-emit-project --format requirements-txt -o requirements.txt`
  (the pre-commit hook does this). CI fails if they diverge — Dependabot PRs for Python deps hit this.
- **Money** is `Decimal` / `numeric(10,2)`, never float.
- **RLS** is enabled on `fiados` with no policies, to close Supabase's public REST API; the app connects as
  table owner and is unaffected. New tables should do the same.
- `/api/debug/erro` exists only when `ENABLE_DEBUG_ROUTES=true` (for testing Sentry).
