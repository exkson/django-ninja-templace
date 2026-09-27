from django.http import HttpRequest
from ninja import Router

from core.services.auth import auth_service
from web.views.schemas.auth import (
    ActivateRequest,
    LoginOtpRequest,
    LoginOtpResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    SessionResponse,
)
from web.views.schemas.shared import AuthErrorResponse, ValidationErrorResponse

router = Router(tags=["auth"])


def _extract_client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@router.post(
    "register",
    response={200: RegisterResponse, 400: ValidationErrorResponse},
)
async def register(request: HttpRequest, body: RegisterRequest):
    return await auth_service.register(body.dict(), ip=_extract_client_ip(request))


@router.post(
    "activate",
    response={200: SessionResponse, 400: ValidationErrorResponse},
)
async def activate(request: HttpRequest, body: ActivateRequest):
    return await auth_service.activate(body.dict())


@router.post(
    "login",
    response={
        200: SessionResponse,
        400: ValidationErrorResponse,
        401: AuthErrorResponse,
    },
)
async def login(request: HttpRequest, body: LoginRequest):
    return await auth_service.login(body.dict())


@router.post(
    "login/otp",
    response={
        200: LoginOtpResponse,
        400: ValidationErrorResponse,
        401: AuthErrorResponse,
    },
)
async def login_otp(request: HttpRequest, body: LoginOtpRequest):
    return await auth_service.login_otp(body.dict())


@router.post(
    "refresh",
    response={200: SessionResponse, 401: AuthErrorResponse},
)
async def refresh(request: HttpRequest, body: RefreshRequest):
    return await auth_service.refresh(body.refresh_token)
