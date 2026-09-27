---
name: define-tests
description: Use when adding or modifying tests. Covers the integration / e2e split, async TestCase conventions, the test settings module, mocking notifications and HTTP, fixtures, and drift tests for closed-set fields.
---

# Defining tests

Two tiers, one file per domain in each:

- **Integration**: `core/tests/services/test_<domain>.py`. Call services directly; assert on DB rows, returned payloads and notification calls.
- **E2E**: `web/tests/e2e/test_<domain>.py`. Drive the HTTP stack via `web/tests/client.py::TestClient`.

## Test settings

`scripts/test.sh` exports `DJANGO_SETTINGS_MODULE=config.settings_test`, which pins I/O to fakes: locmem email (`django.core.mail.outbox`), console WhatsApp, an unroutable geo URL, a fixed JWT secret, the MD5 hasher, and no logging. Don't re-apply `@override_settings` for those. When you add a new external integration, pin its fake in `config/settings_test.py`.

## TestCase basics

- `django.test.TestCase` with `async def test_...` methods.
- `asyncSetUp` is not called by Django's `TestCase`; build fixtures with small `async def _helper()` functions.
- Helpers: `core.tests.helpers.acreate_user(**overrides)` (active user, password `password123`) and `force_latest_otp_code(user, "123456")` (pin the hashed OTP to a known value).
- `core.tests.faker.faker` for unique emails (`faker.unique.email()`).

## Mocking

Patch the specific `notification_manager` method:

```python
NOTIFY_BANNED = "core.services.notifications.notification_manager.send_account_banned"


@patch(NOTIFY_BANNED, new_callable=AsyncMock)
async def test_bans_and_notifies(self, notify): ...
```

For HTTP-backed integrations use `httpx.MockTransport`; never make real network calls.

## E2E client

```python
def _authed(user) -> TestClient:
    token = auth_service._create_token_pair(user)["access_token"]
    return TestClient().authenticate_as(token)
```

Keep this helper in the test module; `TestClient` takes raw token strings only.

## Drift tests

For every `XChoices` + `X = Literal[...]` pair, add to `web/tests/test_schemas.py`:

```python
self.assertEqual(set(get_args(X)), set(XChoices.values))
```

## Async ORM gotchas

- Accessing `obj.fk.field` triggers a sync query; use `select_related` or `obj.fk_id`.
- Use `aget`, `acreate`, `acount`, `arefresh_from_db`, `asave`. Don't mix sync and async ORM in the same scope.

## Running

```bash
./scripts/test.sh
./scripts/test.sh core.tests.services.test_auth
uv run ruff check . && uv run ruff format --check .
```
