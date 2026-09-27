---
name: define-web
description: Use when adding or modifying routes in web/views/ or web/admin/, schemas in */schemas/, or anything else under web/. Covers routing, response contract, pagination and exception-status mapping.
---

# Defining the web layer

The web layer is a **thin gate**: extract HTTP primitives, call a service, return its output. No business logic. No try/except.

## Structure

- Public/user routers: `web/views/<domain>.py`; staff routers: `web/admin/<domain>.py`. Each has `router = Router(tags=["<domain>"])`.
- Schemas: `web/views/schemas/<domain>.py` / `web/admin/schemas/<domain>.py`, inheriting `ninja.Schema`.
- Mount in [config/api.py](../../../config/api.py) via `api.add_router("<prefix>", router)`.
- Unauthenticated routes: add their prefix to `JWT_PUBLIC_PATH_PREFIXES` in [config/settings.py](../../../config/settings.py).

## Endpoint signature

- JSON body: `async def name(request: HttpRequest, body: BodySchema)`, then pass `body.dict()` (or `exclude_unset=True` for PATCH).
- Multipart: `field: str = Form(...)`, `file: UploadedFile = File(...)`.
- Pull primitives from `request` (`request.user`, IP) and pass `user=request.user` **last**.

## Response contract: document every status

For each route, scan **only the first level** of the called service for raises:

| Raise                              | Status | Schema (`web/views/schemas/shared.py`) |
| ---------------------------------- | ------ | -------------------------------------- |
| `ValidationError` / `*Validator.validate(...)` | 400 | `ValidationErrorResponse`   |
| `AuthenticationException`          | 401    | `AuthErrorResponse`                    |
| `ForbiddenError`                   | 403    | `ForbiddenErrorResponse`               |
| `NotFoundError`                    | 404    | `NotFoundErrorResponse`                |

Don't document 422 (Ninja parse errors, global) or middleware 401s.

```python
@router.post(
    "/users/{user_id}/ban",
    response={200: BanStatusResponse, 403: ForbiddenErrorResponse, 404: NotFoundErrorResponse},
)
```

## Schemas

- Reuse shared schemas: `UserBrief`, `PaginatedResponse[T]` and the error responses. Don't invent new error shapes.
- Optional fields: `field: type | None = None`.
- Closed-set fields are typed with the `Literal` from `core.models` (e.g. `OTPChannelValue`), never bare `str`.

## Paginated lists

```python
@router.get(
    "/users",
    response={
        200: AdminUserListResponse,
        400: ValidationErrorResponse,
        403: ForbiddenErrorResponse,
    },
)
async def list_(
    request,
    search: str | None = None,
    page: int = PAGE_DEFAULT,
    page_size: int = LIST_PAGE_SIZE_DEFAULT,
):
    items, total = await list_users(
        search=search, page=page, page_size=page_size, user=request.user
    )
    return {
        "items": [admin_user_payload(u) for u in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
```

Response schema: `class AdminUserListResponse(PaginatedResponse[AdminUserResponse]): pass`. Import the defaults from `core.services.pagination`; bound checks live in the service.

Working example: [web/admin/users.py](../../../web/admin/users.py).

## Hard rules

- Never `try/except` in views.
- No business logic, no ORM queries in views.
- No `core` imports inside `web/tests/client.py`.
