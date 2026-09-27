from django.utils import timezone
from django.utils.translation import gettext as _

from core.exceptions import ValidationError
from core.models import OTPCode, User
from core.services.notifications import notification_manager


async def issue_for_activation(user: User, channel: str) -> OTPCode:
    """Create an OTP for the register/activate flow and deliver it on
    *channel* (the channel of the identifier the user typed)."""
    otp, code = OTPCode.issue(user, channel)
    await otp.asave()
    await notification_manager.send_activation_otp_code(user, code, channel)
    return otp


async def issue_for_login(user: User) -> tuple[OTPCode, str]:
    """Create an OTP for the OTP-login flow and deliver it on the user's
    preferred channel. Returns ``(otp, channel)``."""
    channel = notification_manager.preferred_channel(user)
    otp, code = OTPCode.issue(user, channel)
    await otp.asave()
    await notification_manager.send_login_otp_code(user, code)
    return otp, channel


async def verify(user: User, code: str) -> OTPCode:
    otp = (
        await OTPCode.objects.filter(user=user, consumed_at__isnull=True)
        .order_by("-created_at")
        .afirst()
    )
    if otp is None:
        raise ValidationError({"code": [_("No pending code. Request a new one.")]})
    if otp.is_expired():
        raise ValidationError({"code": [_("Code has expired. Request a new one.")]})
    if otp.is_exhausted():
        raise ValidationError({"code": [_("Too many attempts. Request a new one.")]})

    otp.attempts += 1
    if not otp.matches(code):
        await otp.asave(update_fields=["attempts"])
        raise ValidationError({"code": [_("Invalid code.")]})

    otp.consumed_at = timezone.now()
    await otp.asave(update_fields=["attempts", "consumed_at"])
    return otp
