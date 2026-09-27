---
name: define-services
description: Use when adding or modifying functions and classes in core/services/. Covers the primitives rule, async ORM, validators, exceptions, pagination, notifications and background jobs.
---

# Defining services

Services are the **behaviour layer**. Business logic, input validation, permission/state guards and side effects all live here. Views are thin gates; services own correctness.

## Boundary contract

- **Primitives only**: accept `str`, `int`, `dict` or model instances. Never `HttpRequest`, never a Ninja `Schema`.
- **The acting account comes last and is named `user`.** Not `actor`, `caller` or `me`. When the function has keyword-only params, `user` is the final required keyword-only one.
  - ✅ `async def ban_user(user_id: str, reason: str = "", *, user: User)`
  - ❌ `async def ban_user(actor: User, user_id: str)`
- **All async**: `aget` / `acreate` / `afirst` / `asave` / `acount`. Wrap sync-only APIs (`check_password`, `set_password`) in `sync_to_async`.
- **No HTTP vocabulary**: no status codes in names, comments, docstrings or messages. `web/exc_handlers.py` owns that mapping.
- **Imports at module top.** Fix circular imports structurally, not with in-function imports.

## Input validation

Define a Pydantic model + validator in `core/services/validators/<domain>.py`:

```python
class _CreateProjectV(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    status: ProjectStatusValue = "draft"  # Literal from core.models


class CreateProjectValidator(BaseValidator[_CreateProjectV]):
    validation_class = _CreateProjectV
```

Call it first: `validated = CreateProjectValidator.validate(data)`. Failures raise `core.exceptions.ValidationError` automatically.

## Exceptions to raise

- `ValidationError({"field": [_("msg")]})`: input/state validation. Use the `"detail"` key only for whole-request errors.
- `ForbiddenError(_("..."))`: role- or state-based denial.
- `NotFoundError(_("..."))`: missing resource **or** one the user may not see (deliberately indistinguishable).
- `AuthenticationException(_("..."), code="...")`: credential/token failures (auth only).

Don't `try/except` domain exceptions in services. Translate third-party exceptions (SDKs, state machines, httpx) into domain exceptions at the lowest helper that knows the operation. If you add a new exception type, put it in `core/exceptions.py` and register its handler in `web/exc_handlers.py`.

## Return shape

- For API consumers: a `dict` built by a small `<thing>_payload(model)` helper (see `me_payload` in [core/services/users.py](../../../core/services/users.py)). Never include admin-only fields (e.g. `internal_notes`) in public payloads.
- For internal callers: the model instance.

## Pagination

List services use [core/services/pagination.py](../../../core/services/pagination.py):

- Validator inherits `PaginationParams` (don't redeclare `page` / `page_size`).
- Apply filters and ordering, then `return await paginate(queryset, page=validated.page, page_size=validated.page_size)` → `(items, total)`.

Working example: `list_users` in [core/services/users.py](../../../core/services/users.py).

## Notifications

Never build emails/messages inline. Add a template `core/templates/templated_email/<name>.email` (`subject` / `plain` / `html` blocks, English, `{% blocktrans %}`), then a `send_<event>` method on `NotificationManager` in [core/services/notifications.py](../../../core/services/notifications.py). Use `preferred_channel(user)` unless the flow dictates the channel. `app_name` is in every template context.

## Background jobs

Recurring work is a no-arg async function registered in `JOBS` in [core/services/jobs.py](../../../core/services/jobs.py) as `(fn, trigger, trigger_kwargs)`. It's fired by `manage.py runscheduler`.

## i18n

Use `from django.utils.translation import gettext as _` in services (resolved at raise time). After adding strings, run `./scripts/compile-messages.sh` and fill in `core/locale/fr/LC_MESSAGES/django.po`.

## Structure

- Module-level async functions for stateless services (`core/services/users.py`).
- Class + singleton when config/state is shared (`auth_service = AuthService()`).
