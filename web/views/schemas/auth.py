from ninja import Schema

from core.models import OTPChannelValue
from web.views.schemas.shared import UserBrief


class RegisterRequest(Schema):
    identifier: str


class RegisterResponse(Schema):
    channel: OTPChannelValue
    expires_at: str


class ActivateRequest(Schema):
    identifier: str
    code: str


class LoginRequest(Schema):
    identifier: str
    password: str


class LoginOtpRequest(Schema):
    identifier: str


class RefreshRequest(Schema):
    refresh_token: str


class LoginOtpResponse(Schema):
    channel: OTPChannelValue
    expires_at: str


class SessionResponse(Schema):
    access_token: str
    refresh_token: str
    user: UserBrief
