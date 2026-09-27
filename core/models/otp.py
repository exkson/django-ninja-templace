import hashlib
import secrets
from datetime import timedelta
from typing import Literal

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models.mixins import ULIDMixin

OTP_CODE_TTL = timedelta(minutes=10)
MAX_OTP_ATTEMPTS = 5
CODE_LENGTH = 6


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


class OTPChannel(models.TextChoices):
    EMAIL = "email", _("Email")
    PHONE = "phone", _("Phone")


# Keep in sync with OTPChannel.values
OTPChannelValue = Literal["email", "phone"]


class OTPCode(ULIDMixin):
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="otp_codes",
        verbose_name=_("user"),
    )
    channel = models.CharField(_("channel"), max_length=8, choices=OTPChannel.choices)
    code_hash = models.CharField(_("code hash"), max_length=64)
    expires_at = models.DateTimeField(_("expires at"))
    consumed_at = models.DateTimeField(_("consumed at"), null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)

    class Meta:
        verbose_name = _("OTP code")
        verbose_name_plural = _("OTP codes")
        indexes = [
            models.Index(fields=["user", "consumed_at"]),
        ]

    @classmethod
    def issue(cls, user, channel: str) -> tuple["OTPCode", str]:
        code = _generate_code()
        otp = cls(
            user=user,
            channel=channel,
            code_hash=_hash_code(code),
            expires_at=timezone.now() + OTP_CODE_TTL,
        )
        return otp, code

    def matches(self, code: str) -> bool:
        return _hash_code(code) == self.code_hash

    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_exhausted(self) -> bool:
        return self.attempts >= MAX_OTP_ATTEMPTS
