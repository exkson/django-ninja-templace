from typing import Self

from asgiref.sync import sync_to_async
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from core.models.mixins import ULIDMixin


def get_default_parameters() -> dict:
    return {"notifications": {"preferred_channel": "email"}}


class UserManager(BaseUserManager):
    """Users are identified by email and/or phone — at least one required."""

    def create_user(
        self,
        email: str = "",
        phone: str = "",
        password: str | None = None,
        **extra_fields,
    ):
        if not email and not phone:
            raise ValueError(_("At least one of email or phone is required."))
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, "", password, **extra_fields)

    async def acreate_user(
        self,
        phone: str = "",
        email: str = "",
        password: str | None = None,
        **extra_fields,
    ):
        """Async variant — for use inside ``async def test_...`` methods."""
        return await sync_to_async(self.create_user)(
            phone=phone, email=email, password=password, **extra_fields
        )

    async def acreate_superuser(self, email, password, **extra_fields) -> Self:
        """Async variant — for use inside ``async def test_...`` methods."""
        return await sync_to_async(self.create_superuser)(
            email=email, password=password, **extra_fields
        )


class User(ULIDMixin, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("email address"), blank=True, default="")
    phone = models.CharField(_("phone number"), max_length=20, blank=True, default="")
    first_name = models.CharField(
        _("first name"), max_length=150, blank=True, default=""
    )
    last_name = models.CharField(_("last name"), max_length=150, blank=True, default="")
    country = models.CharField(
        _("country"),
        max_length=2,
        blank=True,
        default="",
        help_text=_("ISO 3166-1 alpha-2 code; populated from IP geocoding."),
    )
    internal_notes = models.TextField(
        _("internal notes"),
        blank=True,
        default="",
        help_text=_("Admin-only notes; never exposed via the public API."),
    )
    parameters = models.JSONField(
        _("parameters"),
        blank=True,
        default=get_default_parameters,
        help_text=_(
            "User-configurable settings (e.g. notifications.preferred_channel)."
        ),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into the admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=False,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Activated after successful OTP verification."
        ),
    )
    banned_at = models.DateTimeField(
        _("banned at"),
        null=True,
        blank=True,
        help_text=_(
            "Set by staff when the account is banned; cleared on unban. "
            "A banned account's token is rejected at authentication time."
        ),
    )
    ban_reason = models.TextField(
        _("ban reason"),
        blank=True,
        default="",
        help_text=_("Staff-supplied reason recorded when the account is banned."),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=~Q(email=""),
                name="core_user_unique_nonempty_email",
            ),
            models.UniqueConstraint(
                fields=["phone"],
                condition=~Q(phone=""),
                name="core_user_unique_nonempty_phone",
            ),
        ]

    @cached_property
    def is_banned(self) -> bool:
        return self.banned_at is not None

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name or self.email or self.phone
