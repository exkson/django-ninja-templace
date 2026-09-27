from ninja import Schema
from pydantic import AwareDatetime

from web.views.schemas.shared import PaginatedResponse


class BanUserRequest(Schema):
    reason: str = ""


class AdminUserResponse(Schema):
    id: str
    first_name: str
    last_name: str
    country: str
    email: str
    phone: str
    joined_at: AwareDatetime
    last_login: AwareDatetime | None = None
    is_banned: bool
    is_active: bool
    is_staff: bool
    is_superuser: bool


class AdminUserListResponse(PaginatedResponse[AdminUserResponse]):
    pass


class BanStatusResponse(Schema):
    id: str
    email: str
    phone: str
    is_banned: bool
    banned_at: AwareDatetime | None = None
    ban_reason: str = ""
