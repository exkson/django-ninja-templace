from django.http import HttpRequest
from ninja import Router

from core.services.users import me_payload, patch_me
from web.views.schemas.shared import ValidationErrorResponse
from web.views.schemas.users import PatchMeRequest, UserMeResponse

router = Router(tags=["users"])


@router.get("me", response=UserMeResponse)
async def get_me(request: HttpRequest):
    return me_payload(request.user)


@router.patch(
    "me",
    response={200: UserMeResponse, 400: ValidationErrorResponse},
)
async def patch_me_endpoint(request: HttpRequest, body: PatchMeRequest):
    return await patch_me(body.dict(exclude_unset=True), user=request.user)
