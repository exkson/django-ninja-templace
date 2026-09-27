from datetime import datetime

from django.http import HttpRequest
from ninja import Router

from core.services.pagination import LIST_PAGE_SIZE_DEFAULT, PAGE_DEFAULT
from core.services.users import (
    admin_user_payload,
    ban_user,
    get_user,
    list_users,
    unban_user,
)
from web.admin.schemas.users import (
    AdminUserListResponse,
    AdminUserResponse,
    BanStatusResponse,
    BanUserRequest,
)
from web.views.schemas.shared import (
    ForbiddenErrorResponse,
    NotFoundErrorResponse,
    ValidationErrorResponse,
)

router = Router(tags=["admin"])


@router.get(
    "/users",
    response={
        200: AdminUserListResponse,
        400: ValidationErrorResponse,
        403: ForbiddenErrorResponse,
    },
)
async def list_(
    request: HttpRequest,
    search: str | None = None,
    country: str | None = None,
    is_staff: bool | None = None,
    is_banned: bool | None = None,
    joined_after: datetime | None = None,
    joined_before: datetime | None = None,
    page: int = PAGE_DEFAULT,
    page_size: int = LIST_PAGE_SIZE_DEFAULT,
):
    items, total = await list_users(
        search=search,
        country=country,
        is_staff=is_staff,
        is_banned=is_banned,
        joined_after=joined_after,
        joined_before=joined_before,
        page=page,
        page_size=page_size,
        user=request.user,
    )
    return {
        "items": [admin_user_payload(u) for u in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/users/{user_id}",
    response={
        200: AdminUserResponse,
        403: ForbiddenErrorResponse,
        404: NotFoundErrorResponse,
    },
)
async def detail(request: HttpRequest, user_id: str):
    found = await get_user(user_id, user=request.user)
    return admin_user_payload(found)


@router.post(
    "/users/{user_id}/ban",
    response={
        200: BanStatusResponse,
        403: ForbiddenErrorResponse,
        404: NotFoundErrorResponse,
    },
)
async def ban(request: HttpRequest, user_id: str, payload: BanUserRequest):
    return await ban_user(user_id, payload.reason, user=request.user)


@router.post(
    "/users/{user_id}/unban",
    response={
        200: BanStatusResponse,
        403: ForbiddenErrorResponse,
        404: NotFoundErrorResponse,
    },
)
async def unban(request: HttpRequest, user_id: str):
    return await unban_user(user_id, user=request.user)
