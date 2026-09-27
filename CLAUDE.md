# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Product

Backend-only JSON API built on the django-ninja template. Replace this section with a description of the product, its domains, currency/locale and regulatory constraints once the project starts.

**User identification**: email **and/or** phone (at least one required, either can be used for OTP login).

All user-facing translation strings (`gettext` / `gettext_lazy`, email templates, `{% trans %}` / `{% blocktrans %}`) are written in English as the source language and translated at runtime via `.po` files.

## Architecture

Full reference: **[docs/architecture.md](docs/architecture.md)**. Read it before adding a new feature.

Three layers, **one-way dependencies**:

```
config/ ─► core/ ◄─ web/
```

- **`core/`**: domain. Models, services, middleware, admin, validators, exceptions, tests/services. **MUST NOT import from `web/`.** Service functions take **primitives** (strings, ints, dicts, model instances), never `HttpRequest`.
- **`web/`**: adapter. Ninja routers (`web/views/`, `web/admin/`), request/response schemas, exception-handler registration, HTTP status codes, test HTTP client, e2e tests. May import from `core/`. No business logic lives here.
- **`config/`**: Django project. Settings, urls, `NinjaAPI` wiring. Imports both.
- **`ulid/`**: vendored utility, do not modify.

Single app (`core/`). New domains go as **new modules inside `core/`**, not new Django apps.

## Stack (non-negotiable unless the user says so)

- **django-ninja** (NOT DRF): async routers, `Schema` classes, central exception handlers.
- **Async everywhere**: views, services, ORM (`aget`/`acreate`/`afirst`/`asave`). `sync_to_async` for sync-only methods like `check_password`.
- **ULID primary keys** via `core/models/mixins.py::ULIDMixin`. Never UUID, never auto-int.
- **JWT** via PyJWT (HS256). Bearer header parsed in `core/middleware.py::JWTAuthMiddleware`. Public prefixes in `settings.JWT_PUBLIC_PATH_PREFIXES`.
- **Settings**: single `config/settings.py`, plain `os.getenv()` only. No django-environ, no pydantic-settings.
- **DB**: SQLite dev, PostgreSQL prod (`psycopg>=3`).
- **i18n**: `USE_I18N = True`; `gettext_lazy as _` in models, `gettext as _` in services.
- **uv** for deps. **ruff** with the rule set pinned in `ruff.toml`. Python 3.13.

## Django model conventions

- **Optional string fields use `default=''`, NOT `null=True`.** `blank=True` is fine alongside. Non-string optional fields (FK, Integer, Date, Boolean, JSON) use `null=True` normally.
- All models inherit `ULIDMixin` (gets `id`, `created_at`, `updated_at`).
- Closed-set string fields: `XChoices(models.TextChoices)` + `X = Literal[...]` mirror + drift test in `web/tests/test_schemas.py`.

## Testing

- Integration: `core/tests/services/test_*.py`. Async `TestCase`, call services directly, mock notifications with `AsyncMock`.
- E2E: `web/tests/e2e/test_*.py`. HTTP via `web/tests/client.py::TestClient`. The client takes raw token strings; no core imports inside it.
- Run: `./scripts/test.sh` (all) or `./scripts/test.sh core.tests.services.test_auth` (narrow). Uses `config.settings_test`.

## Commands

```bash
uv sync                                         # install from uv.lock
uv run python manage.py runserver               # dev server :8000
uv run python manage.py makemigrations core
uv run python manage.py migrate
uv run python manage.py runscheduler            # background jobs
./scripts/dev-migrate.sh                        # wipe dev db + regen core migrations
./scripts/seed-dummy-admin.sh                   # admin@example.com / 1234
./scripts/test.sh [labels...]                   # run test suite
./scripts/compile-messages.sh                   # refresh + compile fr catalogue
```

Dep management: `uv add <pkg>` / `uv add --dev <pkg>`. Never hand-edit `uv.lock`.

Required env vars: `SECRET_KEY`, `JWT_SECRET_KEY` (≥32 chars).

## Separation of concerns

Each layer describes its work in its own vocabulary.

- **HTTP concerns belong to `web/` only.** Status codes, HTTP verbs, headers and response shapes must not appear in `core/` (code, comments, docstrings, names, or error messages). The service layer raises domain exceptions (`ValidationError`, `ForbiddenError`, `NotFoundError`, `AuthenticationException`); `web/exc_handlers.py` decides the wire status.
  - ❌ `_transition_or_400`, `# returns 404 if missing`
  - ✅ `_transition_or_reject`, `# raises NotFoundError if missing`
- **Models don't reference services.** Model docstrings use pure domain language.
- **Services don't reference the web layer.** No `HttpRequest`, no Ninja `Schema`, no URL knowledge.
- **The acting account is the last service parameter and is named `user`.**
- **Code stays LLM-agnostic and free of planning leaks.** Don't reference `CLAUDE.md` or `CHANGELOG.md` from source/tests/templates; no "next PR", "deferred until…" in code. `.claude/` is exempt.

## Hard anti-patterns (do NOT)

- Import `web.*` from anywhere in `core/*`.
- Take `HttpRequest` into a service function.
- Bake HTTP status codes into `core/` symbols, comments, docstrings, or messages.
- Use DRF, UUID PKs, django-environ, `null=True` on string fields, sync views/ORM, or business logic in views or model methods.
- Nest apps under `apps/` or `src/`, or create new Django apps for new domains.
- Build notifications inline; add a `send_*` method on `notification_manager`.
