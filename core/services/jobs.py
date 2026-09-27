"""Recurring background jobs fired by the ``runscheduler`` command.

Each entry in :data:`JOBS` is ``(coroutine_function, trigger, trigger_kwargs)``
using APScheduler's trigger vocabulary (``"interval"``, ``"cron"``, ``"date"``).
Jobs are plain async service functions taking no arguments.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from django.utils import timezone

from core.models import OTPCode

logger = logging.getLogger(__name__)

Job = tuple[Callable[[], Awaitable[None]], str, dict]


async def purge_expired_otp_codes() -> None:
    """Delete OTP codes that expired more than a day ago."""
    cutoff = timezone.now() - timedelta(days=1)
    deleted, _ = await OTPCode.objects.filter(expires_at__lt=cutoff).adelete()
    logger.info("purged %d expired OTP codes", deleted)


JOBS: list[Job] = [
    (purge_expired_otp_codes, "cron", {"hour": 3}),
]
