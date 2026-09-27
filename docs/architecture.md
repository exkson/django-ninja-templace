# Architecture

How this project is organised and which conventions decide where code goes. If you're adding a feature and unsure where a piece belongs, the answer is almost certainly here.

The design is opinionated: pragmatic layering, async-first, a domain-agnostic web layer, one Django app.

## 1. Layers at a glance

Three layers, with strict one-way dependencies:

```
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│   config/    │  ──────► │    core/     │ ◄──────  │     web/     │
│   (project)  │          │   (domain)   │          │  (adapter)   │
└──────────────┘          └──────────────┘          └──────────────┘
   wiring only              all business              HTTP infra:
   (settings,               logic: models,            routers, schemas,
    urls, api)              services,                 exception
                            validators,               handlers, test
                            middleware                client
```

- **`core/`**: the domain layer. Models, services, validators, middleware, admin, domain exceptions, integration tests. All business logic lives here.
- **`web/`**: the adapter layer. Ninja routers and request/response schemas, exception-handler registration, HTTP status-code constants, the e2e test client, e2e tests. No business logic, ever.
- **`config/`**: the Django project package. Settings, URL routing, the `NinjaAPI` instance. Just wiring.
- **`ulid/`**: vendored ULID utility. Never modify.
- **`scripts/`**: shell helpers. **`docs/`**: this document and the frontend error contract.

### The dependency rule

**`core/` must not import from `web/`. Full stop.**

`web/` may import from `core/`, because it's the adapter and has to know the domain it adapts. `config/` may import from both; it wires everything together.

If you want to add `from web.something import …` inside `core/`, stop. Either the thing you need belongs in `core/` (exception classes, shared type aliases), so move it there, or the code you're writing is adapter code and belongs under `web/`.

A violation of this rule is a bug even if the tests pass.

## 2. The `core/` layer

One Django app holds everything. New domains become **new modules inside `core/`**, not new apps:

```
core/
├── apps.py                         # CoreConfig
├── admin.py                        # Django admin registration
├── middleware.py                   # JWTAuthMiddleware (reads token, calls service)
├── exceptions.py                   # ForbiddenError, NotFoundError, ValidationError, AuthenticationException
├── validators.py                   # BaseValidator[T] generic base
├── models/
│   ├── __init__.py                 # re-exports
│   ├── mixins.py                   # ULIDMixin
│   ├── user.py                     # User + UserManager (email and/or phone)
│   └── otp.py                      # OTPCode, OTPChannel (+ OTPChannelValue Literal)
├── services/
│   ├── auth.py                     # AuthService: register, activate, login, login_otp, refresh, authenticate
│   ├── users.py                    # patch_me, list_users, get_user, ban_user, unban_user + payload helpers
│   ├── otp.py                      # issue_for_activation, issue_for_login, verify
│   ├── notifications.py            # NotificationManager (per-event send_* methods)
│   ├── whatsapp.py                 # WhatsAppClient protocol + ConsoleWhatsAppClient
│   ├── geo.py                      # lookup_country(ip)
│   ├── pagination.py               # PaginationParams mixin + paginate()
│   ├── shared.py                   # resolve_user_by_identifier
│   ├── jobs.py                     # JOBS list consumed by `runscheduler`
│   └── validators/
│       ├── auth.py                 # parse_identifier + auth validators
│       └── users.py                # PatchMeValidator, ListUsersValidator
├── management/commands/runscheduler.py
├── templates/templated_email/      # *.email templates (subject / plain / html blocks)
├── locale/fr/LC_MESSAGES/          # French catalogue
├── tests/
│   ├── faker.py                    # shared Faker instance
│   ├── helpers.py                  # acreate_user, force_latest_otp_code
│   └── services/test_*.py          # integration tests
└── migrations/
```

### Models

- All concrete models inherit `ULIDMixin` (`core/models/mixins.py`), which gives a 26-char ULID `id`, `created_at` and `updated_at`. No UUID, no auto-int.
- One file per domain inside `core/models/`; `__init__.py` re-exports public names.
- Optional string fields use `default=''`, **never** `null=True`. Optional non-string fields (FKs, ints, dates, JSON) use `null=True` normally.
- Closed-set string fields get both an `XChoices(models.TextChoices)` class (the storage contract) and an `X = Literal[...]` mirror (the type contract used by validators and schemas), plus a drift test in `web/tests/test_schemas.py`. See `OTPChannel` / `OTPChannelValue`.
- `User` is identified by email **and/or** phone; at least one is required, enforced in `UserManager.create_user`. Uniqueness-when-non-empty is enforced via `Meta.constraints = [UniqueConstraint(..., condition=~Q(field=""))]`, which conflicts with Django's `auth.E003` check. That check is silenced in `config/settings.py::SILENCED_SYSTEM_CHECKS`.

### Services: the primitives rule

Service functions accept **primitives** (strings, ints, dicts, model instances). They never take `HttpRequest`, Ninja `Schema` instances, or anything else HTTP-shaped.

```python
# ✅
async def register(self, data: dict, ip: str = "") -> dict: ...
async def ban_user(user_id: str, reason: str = "", *, user: User) -> dict: ...


# ❌
async def register(self, data: dict, request: HttpRequest) -> dict: ...
```

The account acting on the call is always the **last** parameter and is named **`user`**.

The web layer (views + middleware) is the **only** place allowed to touch `HttpRequest`. It extracts IPs, Bearer tokens, query params and so on, then passes primitives down. See `web/views/auth.py::_extract_client_ip` and `core/middleware.py::_extract_bearer_token`.

Why:
- Services are testable without `RequestFactory`.
- Services are reusable from management commands, scheduled jobs and scripts.
- The domain stays transport-agnostic.

### Validators

Pydantic-based, wrapped in `BaseValidator[T]` (`core/validators.py`). Declare a Pydantic `BaseModel`, subclass `BaseValidator[...]` with `validation_class = YourModel`, and call `.validate(data)` first thing in the service. Pydantic errors become `core.exceptions.ValidationError` with a flat `{field: [messages]}` shape.

### Middleware

`core/middleware.py::JWTAuthMiddleware`:
- Skips paths starting with any prefix in `settings.JWT_PUBLIC_PATH_PREFIXES`.
- Extracts the `Authorization: Bearer …` token and calls `auth_service.authenticate(token)`.
- Responds `401 {"code": "invalid-token"}` when no active user matches, and `401 {"code": "banned-account"}` when the user is banned.
- Otherwise sets `request.user`.

### Exceptions

All domain exceptions live in `core/exceptions.py`; the wire mapping lives in `web/exc_handlers.py`:

| Exception                 | Status | Body                                      |
|---------------------------|--------|-------------------------------------------|
| `ValidationError`         | 400    | `{field: [messages]}`                     |
| `AuthenticationException` | 401    | `{detail, code: AuthExceptionCode}`       |
| `ForbiddenError`          | 403    | `{detail}`                                |
| `NotFoundError`           | 404    | `{detail}`                                |

Never define exceptions in `web/`. When you add a domain exception, register its handler in `web/exc_handlers.py`.

### Notifications

`core/services/notifications.py::notification_manager` is the only way to reach users. Templates own the wording; per-event `send_*` methods own the template and channel policy; `notify` / `_notify_raw` dispatch over email (Django mail) or WhatsApp (pluggable client). Delivery failures are logged and swallowed. Notifications never break the business flow.

### Background jobs

`python manage.py runscheduler` runs APScheduler in its own long-lived process (a separate supervisord program in the container). Register jobs in `core/services/jobs.py::JOBS` as `(async_fn, trigger, trigger_kwargs)`.

## 3. The `web/` layer

```
web/
├── status.py                       # HTTP status-code constants (vendored)
├── exc_handlers.py                 # setup_handlers(api): domain exceptions → HTTP
├── views/
│   ├── auth.py                     # /api/auth/*
│   ├── users.py                    # /api/users/me (GET + PATCH)
│   └── schemas/
│       ├── shared.py               # UserBrief, PaginatedResponse[T], error schemas
│       ├── auth.py
│       └── users.py
├── admin/
│   ├── users.py                    # /api/admin/users (list, detail, ban, unban)
│   └── schemas/users.py
└── tests/
    ├── client.py                   # TestClient (wraps django.test.AsyncClient)
    ├── test_schemas.py             # Literal ↔ Choices drift tests
    └── e2e/test_*.py
```

Each handler:
1. Takes a Ninja `Schema` body and/or typed query/path params.
2. Extracts HTTP-layer primitives from `request` (IP, `request.user`).
3. Calls a service with primitives.
4. Returns the service's dict (or builds the paginated envelope).

Every route declares in `response={...}` each status its service can raise at the first level. No `try/except` in views.

`web/tests/client.py::TestClient` must stay domain-agnostic: it takes raw Bearer token strings and never imports from `core`. E2E tests that need an authenticated client define a local helper:

```python
def _authed(user) -> TestClient:
    token = auth_service._create_token_pair(user)["access_token"]
    return TestClient().authenticate_as(token)
```

## 4. The `config/` layer

- `config/settings.py` is the **only** file that reads env vars, using plain `os.getenv`.
- `config/settings_test.py` pins every I/O backend to an in-process fake; `scripts/test.sh` selects it.
- `config/api.py` instantiates `NinjaAPI`, calls `setup_handlers(api)` and mounts routers.
- `config/urls.py` mounts `admin/` and `api/`.

## 5. Pluggable integrations

| Integration  | Setting               | Default                                          | Swap for                             |
|--------------|-----------------------|--------------------------------------------------|--------------------------------------|
| Email        | `EMAIL_BACKEND`       | SMTP (`console` in `.env.example`)               | Any Django email backend             |
| WhatsApp     | `WHATSAPP_BACKEND`    | `core.services.whatsapp.ConsoleWhatsAppClient`   | Twilio / Meta Cloud API client class |
| IP → country | `GEO_IP_PROVIDER_URL` | `https://ipapi.co/{ip}/country/`                 | MaxMind GeoLite2, paid API           |

The WhatsApp backend is loaded by dotted path; the class needs only `async def send(phone: str, message: str) -> None`. Geo failures fall back to `DEFAULT_COUNTRY`; registration never blocks on geocoding.

## 6. Testing strategy

- **Integration**: `core/tests/services/test_*.py`. Async `TestCase`, call services directly, mock `notification_manager.send_*` with `AsyncMock`.
- **E2E**: `web/tests/e2e/test_*.py`. Go through the real URL conf and middleware via `TestClient`.

Run with `./scripts/test.sh`, or pass dotted labels to narrow the run. Django's stdlib runner only; no pytest.

## 7. Auth flow

```
POST /api/auth/register {identifier}
  web/views/auth.py::register  → _extract_client_ip(request)
  core/services/auth.py::register
    RegisterValidator → parse_identifier → ("email"|"phone", normalised)
    find or create User (country from lookup_country(ip))
    issue_for_activation → notification_manager.send_activation_otp_code
  ← {channel, expires_at}

POST /api/auth/activate {identifier, code}
  verify OTP → activate user → {access_token, refresh_token, user}

POST /api/auth/login {identifier, password}      → session
POST /api/auth/login/otp {identifier}             → OTP on preferred channel, then /activate
POST /api/auth/refresh {refresh_token}            → new access token

GET /api/users/me  (Authorization: Bearer <access>)
  JWTAuthMiddleware → auth_service.authenticate(token) → request.user
```

## 8. Conventions catalogue

| Concern                    | Rule                                                                                  |
|----------------------------|---------------------------------------------------------------------------------------|
| App layout                 | One app (`core/`). New domains = new modules inside it.                               |
| Layer imports              | `core/` never imports `web/`.                                                         |
| Service signatures         | Primitives only; acting account is the last param, named `user`.                      |
| HTTP vocabulary            | Status codes, verbs and headers appear only in `web/` (code, names, docstrings).      |
| Primary keys               | ULIDs via `ULIDMixin`.                                                                |
| Optional string fields     | `default=''`, never `null=True`.                                                      |
| Closed sets                | `XChoices` + `X = Literal[...]` + drift test.                                         |
| Exceptions                 | Defined in `core/exceptions.py`, mapped in `web/exc_handlers.py`.                     |
| Settings                   | Single `config/settings.py`, `os.getenv()` only.                                      |
| Async                      | Views, services, ORM. `sync_to_async` for sync-only APIs.                             |
| i18n                       | English source strings; `gettext` in services, `gettext_lazy` in models.              |
| Pagination                 | `PaginationParams` + `paginate()` in services, `PaginatedResponse[T]` in schemas.     |
| Deps / lint                | `uv`, `ruff`.                                                                         |

## 9. Explicitly *not* our convention

DRF · django-environ / pydantic-settings · factory_boy · pytest · UUID or auto-int PKs · multiple Django apps · `apps/` or `src/` layouts · business logic in views or model methods · session auth or DRF tokens.
