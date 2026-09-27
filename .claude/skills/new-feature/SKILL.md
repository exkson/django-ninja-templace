---
name: new-feature
description: Use when implementing a new feature end-to-end (data + service + endpoint + tests). Orchestrates define-data-models, define-services, define-tests and define-web in the right order.
---

# Implementing a new feature

1. **Data**: apply `define-data-models`. Add models in `core/models/<domain>.py` (ULIDMixin; `XChoices` + `Literal` + drift test for closed sets) and re-export them.
2. **Migrate**: `uv run python manage.py makemigrations core && uv run python manage.py migrate` (or `./scripts/dev-migrate.sh` before first deploy).
3. **Service**: apply `define-services`. Validator in `core/services/validators/<domain>.py`, logic in `core/services/<domain>.py`, notifications via `notification_manager`.
4. **Integration tests**: apply `define-tests` → `core/tests/services/test_<domain>.py`.
5. **Endpoint**: apply `define-web`. Schemas + router, mounted in `config/api.py`; public prefixes in `JWT_PUBLIC_PATH_PREFIXES`.
6. **Document errors**: map each first-level raise and `*Validator.validate(...)` call to a status in `response={...}`.
7. **E2E tests**: `web/tests/e2e/test_<domain>.py`.
8. **i18n**: `./scripts/compile-messages.sh`, then fill in the French `msgstr`s and compile again.
9. **Verify**: `./scripts/test.sh && uv run ruff check . && uv run ruff format --check .`

## Cross-cutting reminders

- `core/` never imports `web/`; services take primitives, with `user` last.
- HTTP vocabulary stays in `web/`.
- Async everywhere.
- Every user-facing string goes through `_()`.
- No `CLAUDE.md` / `CHANGELOG.md` / planning references in source.
