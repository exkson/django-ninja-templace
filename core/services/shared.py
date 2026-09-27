"""Cross-service helpers shared by multiple ``core.services.*`` modules.

Anything that more than one service needs and that doesn't naturally belong
to a single domain module lives here.
"""

from core.models import User


async def resolve_user_by_identifier(channel: str, identifier: str) -> User | None:
    """Look up a user by *identifier* on the given *channel* (``email``/``phone``).

    Returns ``None`` when no user matches; the caller decides whether that's
    an error or a "not yet registered" case.
    """
    field = "email" if channel == "email" else "phone"
    return await User.objects.filter(**{field: identifier}).afirst()
