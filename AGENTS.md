# Repository Guidelines

## Project Structure & Module Organization
- Core Django logic lives in `interlinker/`: `views.py` and `forms.py` drive the UI flow, `services.py` implements sitemap parsing and link insertion, and `engine_v2/` houses the experimental matching engine covered by `tests/engine_v2/`.
- Templates render from `interlinker/templates/`; shared CSS and images stay in `static/`, while `staticfiles/` is generated output and should remain untouched.
- Reusable business models, throttling middleware, and background helpers sit alongside `migrations/`; project-level settings, URLs, and WSGI/ASGI bootstrap code stay under `interlinker_tool/`, with deployment assets (Dockerfile, `entrypoint.sh`, `.env.example`) at the repo root.

## Build, Test, and Development Commands
- `python manage.py runserver` launches the local dev server on `http://127.0.0.1:8000/` with auto-reload.
- `python manage.py migrate` applies schema changes to the SQLite dev database; run after altering models or pulling new migrations.
- `pytest` executes the Django-aware test suite in `tests/` and reports failures with rich diffs.
- `python manage.py collectstatic --noinput` prepares assets for deployment; verify `STATIC_ROOT` before running in production contexts.
- Container workflow: `docker build -t interlinker .` and `docker run --env-file .env -p 8000:8000 interlinker` start the production stack locally.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, expressive `snake_case` for functions/variables, and `CamelCase` for classes; mirror existing docstring style for public helpers.
- Prefer type hints, as seen in `tests/test_interlinker.py`, to keep services and forms self-documenting.
- Keep templates lean and avoid inline scripts; shared snippets belong in `{% include %}` fragments under `templates/interlinker/partials/` when added.

## Testing Guidelines
- Extend `pytest`-driven `django.test.TestCase` classes for database-aware logic; locate new files under `tests/` and mirror module paths (e.g., `tests/test_services.py`).
- Name tests with intentional behaviour statements such as `test_interlink_html_prioritises_priority_terms` so failures communicate impact.
- Maintain coverage on sitemap parsing, rate limiting, and interlink insertion whenever altering `services.py` or `middleware.py`; add fixtures or factories instead of hard-coded IDs.

## Commit & Pull Request Guidelines
- Keep commits small and imperative (e.g., `Add sitemap retry backoff`), matching the concise history in `git log`.
- Before opening a PR, ensure migrations and `pytest` pass locally, describe the change set, note config or data migrations, and attach UI screenshots or HTML snippets when templates move.
- Link issues or TODO items inline (`Fixes #12`) and flag follow-up work explicitly so agents can triage quickly.

## Security & Configuration Tips
- Store secrets (API keys, admin credentials) in environment variables; never hard-code them in `settings.py` or fixtures.
- Use `.env.example` as the template for required settings; keep `DATABASE_URL` pointed at managed Postgres and rotate `DJANGO_SECRET_KEY` regularly.
- When deploying, enable `WHITENOISE` for static serving and configure `ALLOWED_HOSTS`, HTTPS, and rate-limiting thresholds to match the target environment.
