# django-ninja template

An opinionated starter for **async JSON APIs** on Django 6 + django-ninja. It gives you:

- **Strict layering**: `config/` (wiring) → `core/` (domain) ← `web/` (HTTP adapter). Services take primitives and never see a request.
- **Passwordless auth**: OTP sign-up/login on **email and/or phone**, optional password login, **JWT** access/refresh tokens (PyJWT, HS256), and banned-account enforcement in middleware.
- **User model** with **ULID** primary keys, conditional uniqueness on email/phone, JSON preferences.
- **Staff admin API**: paginated, filterable user list, user detail, ban/unban with notification.
- **Notification manager**: templated email (`django-templated-email`) plus a pluggable WhatsApp client, with per-user preferred channel.
- **Uniform error contract**: `ValidationError` → 400 `{field: [msgs]}`, `AuthenticationException` → 401 `{detail, code}`, `ForbiddenError` → 403, `NotFoundError` → 404. See [docs/api-errors.md](docs/api-errors.md).
- **Pydantic validators**, **shared pagination** (`PaginationParams` / `PaginatedResponse[T]`).
- **i18n from day one**: English source strings, French catalogue, `Accept-Language` negotiation.
- **Background jobs**: `manage.py runscheduler` (APScheduler) with a job registry.
- **Tests**: integration (services) + e2e (HTTP) tiers, hermetic test settings, domain-agnostic test client.
- **Ops**: Dockerfile (nginx + gunicorn/uvicorn + scheduler under supervisord), GitHub Actions (ruff + tests, GHCR image push), pre-commit hook.
- **Claude Code skills** in `.claude/skills/` that encode the conventions per layer.

Architecture reference: **[docs/architecture.md](docs/architecture.md)**.

## Start a new project from this template

```bash
cp -r django-ninja-template my-api && cd my-api
rm -rf .git && git init
# rename the package in pyproject.toml, set APP_NAME in .env
cp .env.example .env
uv sync
./scripts/install-hooks.sh
uv run python manage.py migrate
./scripts/seed-dummy-admin.sh            # admin@example.com / 1234
uv run python manage.py runserver        # http://localhost:8000/api/docs
```

If you want different package names than `core` / `web` / `config`, rename them before the first migration: the directories, dotted paths in `config/settings.py`, `manage.py`, `config/asgi.py`, `config/wsgi.py`, `docker/supervisord.conf`, `scripts/*.sh`, `.github/workflows/quality-check.yml`, and the `core.` imports.

## Adding a feature

1. **Model** in `core/models/<domain>.py` (inherit `ULIDMixin`), re-export it from `core/models/__init__.py`, then run `uv run python manage.py makemigrations core`.
2. **Validator** in `core/services/validators/<domain>.py`, **service** in `core/services/<domain>.py`.
3. **Integration tests** in `core/tests/services/test_<domain>.py`.
4. **Schemas** in `web/views/schemas/<domain>.py`, **router** in `web/views/<domain>.py`, mounted in `config/api.py`. Public routes go in `JWT_PUBLIC_PATH_PREFIXES`.
5. **E2E tests** in `web/tests/e2e/test_<domain>.py`.
6. `./scripts/test.sh && uv run ruff check .`

With Claude Code, the `new-feature` skill walks through these steps.

## API surface

| Route                               | Auth   | Purpose                                         |
|-------------------------------------|--------|-------------------------------------------------|
| `POST /api/auth/register`           | public | Create/find user by email or phone, send OTP    |
| `POST /api/auth/activate`           | public | Verify OTP, activate, return tokens             |
| `POST /api/auth/login`              | public | Password login                                  |
| `POST /api/auth/login/otp`          | public | Send login OTP on preferred channel             |
| `POST /api/auth/refresh`            | public | New access token from refresh token             |
| `GET/PATCH /api/users/me`           | user   | Profile read/update (names, password)           |
| `GET /api/admin/users`              | staff  | Paginated list; search, country, staff, banned, joined range |
| `GET /api/admin/users/{id}`         | staff  | User detail                                     |
| `POST /api/admin/users/{id}/ban`    | staff  | Ban with reason (notifies the user)             |
| `POST /api/admin/users/{id}/unban`  | staff  | Lift ban                                        |

## Configuration

All settings come from plain environment variables read in `config/settings.py`. See [.env.example](.env.example) for the full list.

| Variable                                        | Purpose                                  |
|-------------------------------------------------|------------------------------------------|
| `SECRET_KEY`, `JWT_SECRET_KEY` (≥32 chars)      | Required secrets                         |
| `APP_NAME`                                      | Name shown in notifications              |
| `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Runtime / HTTP  |
| `DATABASE_BACKEND` (`sqlite`/`postgres`), `DATABASE_*` | Database                          |
| `ACCESS_TOKEN_DURATION_MINUTES`, `REFRESH_TOKEN_DURATION_DAYS` | Token lifetimes           |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL`                 | Outbound email                           |
| `WHATSAPP_BACKEND`                              | Dotted path to WhatsApp client class     |
| `GEO_IP_PROVIDER_URL`, `DEFAULT_COUNTRY`        | IP → country on sign-up                  |
| `SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD`, `GUNICORN_WORKERS` | Container entrypoint          |

## Scripts

```bash
./scripts/test.sh [labels...]     # test suite under config.settings_test
./scripts/dev-migrate.sh          # wipe dev sqlite + regenerate core migrations
./scripts/seed-dummy-admin.sh     # dev superuser
./scripts/compile-messages.sh     # refresh + compile the French catalogue
./scripts/install-hooks.sh        # ruff pre-commit hook
uv run python manage.py runscheduler
```

## Deployment

`docker build -t my-api .` produces an image where supervisord runs nginx (`:8000`, serving `/static/` and `/media/`), gunicorn with uvicorn workers (`127.0.0.1:8001`), and the scheduler. The entrypoint migrates, collects static files and optionally creates a superuser. `.github/workflows/deploy.yml` runs the quality gate, then pushes the image to GHCR on `dev`, `main` and `v*` tags.
