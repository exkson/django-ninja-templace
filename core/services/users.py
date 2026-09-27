from asgiref.sync import sync_to_async
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from core.exceptions import ForbiddenError, NotFoundError
from core.models import User
from core.services.notifications import notification_manager
from core.services.pagination import (
    LIST_PAGE_SIZE_DEFAULT,
    PAGE_DEFAULT,
    paginate,
)
from core.services.validators.users import ListUsersValidator, PatchMeValidator


async def patch_me(data: dict, *, user: User) -> dict:
    validated = PatchMeValidator.validate(data)
    update_fields: list[str] = []

    if validated.first_name is not None:
        user.first_name = validated.first_name
        update_fields.append("first_name")
    if validated.last_name is not None:
        user.last_name = validated.last_name
        update_fields.append("last_name")
    if validated.password is not None:
        await sync_to_async(user.set_password)(validated.password)
        update_fields.append("password")

    if update_fields:
        await user.asave(update_fields=update_fields)
    return me_payload(user)


async def list_users(
    *,
    search: str | None = None,
    country: str | None = None,
    is_staff: bool | None = None,
    is_banned: bool | None = None,
    joined_after=None,
    joined_before=None,
    page: int = PAGE_DEFAULT,
    page_size: int = LIST_PAGE_SIZE_DEFAULT,
    user: User,
) -> tuple[list[User], int]:
    """Paginated, filtered list of accounts for staff, newest first.

    *search* matches (case-insensitive, substring) any of first name, last
    name, email or phone. *country* is an exact ISO 3166-1 alpha-2 match.
    *is_staff* / *is_banned* filter on role and ban state. *joined_after* /
    *joined_before* bound ``date_joined`` (inclusive).

    *user* is the requesting account. Raises :class:`ForbiddenError` when it
    is not staff.
    """
    if not user.is_staff:
        raise ForbiddenError(_("Only staff can list users."))
    validated = ListUsersValidator.validate(
        {
            "search": search,
            "country": country,
            "is_staff": is_staff,
            "is_banned": is_banned,
            "joined_after": joined_after,
            "joined_before": joined_before,
            "page": page,
            "page_size": page_size,
        }
    )
    queryset = User.objects.all()

    if validated.search and validated.search.strip():
        term = validated.search.strip()
        queryset = queryset.filter(
            Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
            | Q(phone__icontains=term)
        )
    if validated.country:
        queryset = queryset.filter(country__iexact=validated.country)
    if validated.is_staff is not None:
        queryset = queryset.filter(is_staff=validated.is_staff)
    if validated.is_banned is not None:
        queryset = queryset.filter(banned_at__isnull=not validated.is_banned)
    if validated.joined_after is not None:
        queryset = queryset.filter(date_joined__gte=validated.joined_after)
    if validated.joined_before is not None:
        queryset = queryset.filter(date_joined__lte=validated.joined_before)

    queryset = queryset.order_by("-date_joined")
    return await paginate(queryset, page=validated.page, page_size=validated.page_size)


async def get_user(user_id: str, *, user: User) -> User:
    """Fetch a single account for staff.

    *user* is the requesting account. Raises :class:`ForbiddenError` when it
    is not staff, and :class:`NotFoundError` when no account matches *user_id*.
    """
    if not user.is_staff:
        raise ForbiddenError(_("Only staff can view a user."))
    try:
        return await User.objects.aget(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError() from exc


async def ban_user(user_id: str, reason: str = "", *, user: User) -> dict:
    """Ban the account with *user_id*, recording *reason* and notifying them.

    *user* is the requesting account; only staff may ban. Idempotent:
    re-banning an already-banned account is a no-op that returns the current
    state without re-notifying. Raises :class:`ForbiddenError` when *user* is
    not staff, and :class:`NotFoundError` when no account matches *user_id*.
    """
    if not user.is_staff:
        raise ForbiddenError(_("Only staff can ban a user."))
    try:
        target = await User.objects.aget(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError() from exc

    if target.banned_at is not None:
        return ban_status_payload(target)

    target.banned_at = timezone.now()
    target.ban_reason = reason or ""
    await target.asave(update_fields=["banned_at", "ban_reason", "updated_at"])

    await notification_manager.send_account_banned(target, target.ban_reason)
    return ban_status_payload(target)


async def unban_user(user_id: str, *, user: User) -> dict:
    """Lift the ban on the account with *user_id*.

    *user* is the requesting account; only staff may unban. Idempotent:
    unbanning an account that isn't banned is a no-op. Raises
    :class:`ForbiddenError` when *user* is not staff, and
    :class:`NotFoundError` when no account matches *user_id*.
    """
    if not user.is_staff:
        raise ForbiddenError(_("Only staff can unban a user."))
    try:
        target = await User.objects.aget(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError() from exc

    if target.banned_at is None:
        return ban_status_payload(target)

    target.banned_at = None
    target.ban_reason = ""
    await target.asave(update_fields=["banned_at", "ban_reason", "updated_at"])
    return ban_status_payload(target)


def me_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "country": user.country,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def ban_status_payload(user: User) -> dict:
    """Ban state for a staff caller acting on *user*."""
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "is_banned": user.is_banned,
        "banned_at": user.banned_at,
        "ban_reason": user.ban_reason,
    }


def admin_user_payload(user: User) -> dict:
    """Staff-facing view of an account."""
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "country": user.country,
        "email": user.email,
        "phone": user.phone,
        "joined_at": user.date_joined,
        "last_login": user.last_login,
        "is_banned": user.is_banned,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }
