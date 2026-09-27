from ninja import Schema

from web.views.schemas.shared import UserBrief


class UserMeResponse(UserBrief):
    pass


class PatchMeRequest(Schema):
    first_name: str | None = None
    last_name: str | None = None
    password: str | None = None
