from datetime import timedelta
from typing import TypedDict

import jwt
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from core.exceptions import AuthenticationException, ValidationError
from core.models import User
from core.services.geo import lookup_country
from core.services.otp import issue_for_activation, issue_for_login
from core.services.otp import verify as verify_otp
from core.services.shared import resolve_user_by_identifier
from core.services.users import me_payload
from core.services.validators.auth import (
    ActivateValidator,
    LoginOtpValidator,
    LoginValidator,
    RegisterValidator,
    parse_identifier,
)


class TokenPair(TypedDict):
    access_token: str
    refresh_token: str


class AuthService:
    algorithm = "HS256"

    @property
    def jwt_key(self) -> str:
        return settings.JWT_SECRET_KEY

    async def register(self, data: dict, ip: str = "") -> dict:
        """Create the user if new, then (re-)issue an OTP on the provided channel.

        *ip* is used for country geocoding when the user is first seen. The
        caller is responsible for extracting it from wherever the call
        originated.
        """
        validated = RegisterValidator.validate(data)
        channel, identifier = parse_identifier(validated.identifier)

        user = await resolve_user_by_identifier(channel, identifier)
        if user is None:
            country = await lookup_country(ip)
            kwargs: dict = {"country": country}
            if channel == "email":
                kwargs["email"] = identifier
            else:
                kwargs["phone"] = identifier
            user = await User.objects.acreate(**kwargs)

        otp = await issue_for_activation(user, channel)
        return {
            "channel": channel,
            "expires_at": otp.expires_at.isoformat(),
        }

    async def activate(self, data: dict) -> dict:
        """Verify the OTP and return a fresh token pair (activates the user if new)."""
        validated = ActivateValidator.validate(data)
        channel, identifier = parse_identifier(validated.identifier)

        user = await resolve_user_by_identifier(channel, identifier)
        if user is None:
            raise ValidationError({"identifier": [_("Unknown identifier.")]})

        await verify_otp(user, validated.code)

        update_fields = ["last_login"]
        if not user.is_active:
            user.is_active = True
            update_fields.append("is_active")
        user.last_login = timezone.now()
        await user.asave(update_fields=update_fields)
        return self._session_payload(user)

    async def login_otp(self, data: dict) -> dict:
        """Issue an OTP for a registered user to sign in with.

        Unlike ``register``, the OTP is sent on the user's *preferred* channel,
        not the channel of the identifier they typed.
        """
        validated = LoginOtpValidator.validate(data)
        channel, identifier = parse_identifier(validated.identifier)

        user = await resolve_user_by_identifier(channel, identifier)
        if user is None or not user.is_active:
            raise AuthenticationException(
                _("Invalid credentials"), code="invalid-credentials"
            )

        otp, channel = await issue_for_login(user)
        return {
            "channel": channel,
            "expires_at": otp.expires_at.isoformat(),
        }

    async def login(self, data: dict) -> dict:
        """Password-based login. Only works once the user has set a password."""
        validated = LoginValidator.validate(data)
        channel, identifier = parse_identifier(validated.identifier)

        user = await resolve_user_by_identifier(channel, identifier)
        invalid = AuthenticationException(
            _("Invalid credentials"), code="invalid-credentials"
        )

        if user is None or not user.is_active or not user.has_usable_password():
            # Still run the hasher to reduce timing side-channels.
            await sync_to_async(User().set_password)(validated.password)
            raise invalid

        password_ok = await sync_to_async(user.check_password)(validated.password)
        if not password_ok:
            raise invalid
        user.last_login = timezone.now()
        await user.asave(update_fields=["last_login"])
        return self._session_payload(user)

    async def refresh(self, refresh_token: str) -> dict:
        """Exchange a valid refresh token for a fresh access token.

        Raises ``AuthenticationException`` when the token is missing,
        malformed, expired, not a refresh token, or its user is gone or
        deactivated.
        """
        invalid = AuthenticationException(_("Invalid token"), code="invalid-token")
        user = await self._user_from_token(refresh_token, token_type="refresh")
        if user is None:
            raise invalid
        return {
            "access_token": self._create_token_pair(user)["access_token"],
            "refresh_token": refresh_token,
            "user": me_payload(user),
        }

    async def authenticate(self, access_token: str) -> User | None:
        """Resolve *access_token* to an active ``User`` or ``None``."""
        return await self._user_from_token(access_token, token_type="access")

    async def _user_from_token(self, token: str, *, token_type: str) -> User | None:
        if not token:
            return None
        try:
            payload = jwt.decode(token, self.jwt_key, algorithms=[self.algorithm])
        except jwt.PyJWTError:
            return None

        if payload.get("type") != token_type:
            return None
        user_id = payload.get("sub")
        exp = payload.get("exp")
        if not (user_id and exp):
            return None
        if exp < int(timezone.now().timestamp()):
            return None
        try:
            return await User._default_manager.aget(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None

    def _session_payload(self, user: User) -> dict:
        return {**self._create_token_pair(user), "user": me_payload(user)}

    def _create_token_pair(self, user: User) -> TokenPair:
        now = timezone.now()
        access_exp = now + timedelta(minutes=settings.ACCESS_TOKEN_DURATION_MINUTES)
        refresh_exp = now + timedelta(days=settings.REFRESH_TOKEN_DURATION_DAYS)
        access = jwt.encode(
            {"sub": str(user.id), "type": "access", "exp": int(access_exp.timestamp())},
            key=self.jwt_key,
            algorithm=self.algorithm,
        )
        refresh = jwt.encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "exp": int(refresh_exp.timestamp()),
            },
            key=self.jwt_key,
            algorithm=self.algorithm,
        )
        return {"access_token": access, "refresh_token": refresh}


auth_service = AuthService()
