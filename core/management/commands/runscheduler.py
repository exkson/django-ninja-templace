"""Long-lived process: APScheduler firing recurring background jobs.

Runs separately from the ASGI web workers — one process per deployment
(supervisord program, systemd unit, k8s deployment, …). Web workers stay
stateless and never fire scheduled jobs, so a job never fans out across N
gunicorn workers.

The job list lives in :data:`core.services.jobs.JOBS`.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from django.core.management.base import BaseCommand

from core.services.jobs import JOBS

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the long-lived APScheduler that fires recurring background jobs."

    def handle(self, *args, **options):
        asyncio.run(self._run())

    async def _run(self):
        scheduler = AsyncIOScheduler()
        for func, trigger, trigger_kwargs in JOBS:
            scheduler.add_job(
                func,
                trigger,
                id=func.__name__,
                max_instances=1,
                coalesce=True,
                **trigger_kwargs,
            )
            logger.info("scheduled %s (%s %s)", func.__name__, trigger, trigger_kwargs)
        scheduler.start()
        try:
            await asyncio.Event().wait()
        finally:
            scheduler.shutdown(wait=True)
