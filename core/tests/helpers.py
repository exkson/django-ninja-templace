"""Test fixtures shared across service and e2e tests."""

from core.models import OTPCode, User
from core.models.otp import _hash_code
from core.tests.faker import faker


async def acreate_user(**overrides) -> User:
    """Create an active user with sensible defaults. Override any field via kwargs.

    Defaults:
      - email: random unique
      - phone: empty (email-only account)
      - is_active: True  (required for tokens to pass the JWT middleware)
      - password: ``password123`` (usable)
    """
    data = {
        "email": faker.unique.email(),
        "phone": "",
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
        "is_active": True,
        "password": "password123",
        "is_superuser": False,
    }
    data.update(overrides)
    return await User.objects.acreate_user(**data)


async def force_latest_otp_code(user: User, code: str = "123456") -> str:
    """Overwrite the user's most recent OTP so its plaintext is *code*.

    OTPs are stored hashed, so tests can't read the issued code back; this
    pins it to a known value instead.
    """
    otp = await OTPCode.objects.filter(user=user).order_by("-created_at").afirst()
    otp.code_hash = _hash_code(code)
    await otp.asave(update_fields=["code_hash"])
    return code
