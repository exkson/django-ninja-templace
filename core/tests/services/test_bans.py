from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.utils import timezone

from core.exceptions import ForbiddenError, NotFoundError
from core.models import User
from core.services.users import ban_user, unban_user
from core.tests.helpers import acreate_user

NOTIFY_BANNED = "core.services.notifications.notification_manager.send_account_banned"


class BanUserServiceTestCase(TestCase):
    @patch(NOTIFY_BANNED, new_callable=AsyncMock)
    async def test_staff_bans_user_and_notifies(self, notify):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user()

        payload = await ban_user(target.id, "abuse", user=admin)

        self.assertTrue(payload["is_banned"])
        self.assertEqual(payload["ban_reason"], "abuse")
        self.assertIsNotNone(payload["banned_at"])
        notify.assert_awaited_once()
        refreshed = await User.objects.aget(pk=target.pk)
        self.assertIsNotNone(refreshed.banned_at)
        self.assertTrue(refreshed.is_banned)

    @patch(NOTIFY_BANNED, new_callable=AsyncMock)
    async def test_non_staff_cannot_ban(self, notify):
        actor = await acreate_user(is_staff=False)
        target = await acreate_user()

        with self.assertRaises(ForbiddenError):
            await ban_user(target.id, "abuse", user=actor)
        notify.assert_not_awaited()

    @patch(NOTIFY_BANNED, new_callable=AsyncMock)
    async def test_re_ban_is_noop_without_renotifying(self, notify):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user(banned_at=timezone.now(), ban_reason="first")

        payload = await ban_user(target.id, "second", user=admin)

        self.assertTrue(payload["is_banned"])
        self.assertEqual(payload["ban_reason"], "first")
        notify.assert_not_awaited()

    async def test_ban_missing_user_raises_not_found(self):
        admin = await acreate_user(is_staff=True)
        with self.assertRaises(NotFoundError):
            await ban_user("01JABCDEF0000000000000000", "abuse", user=admin)

    async def test_unban_restores_access(self):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user(banned_at=timezone.now(), ban_reason="abuse")

        payload = await unban_user(target.id, user=admin)

        self.assertFalse(payload["is_banned"])
        self.assertIsNone(payload["banned_at"])
        self.assertEqual(payload["ban_reason"], "")
        refreshed = await User.objects.aget(pk=target.pk)
        self.assertFalse(refreshed.is_banned)

    async def test_non_staff_cannot_unban(self):
        actor = await acreate_user(is_staff=False)
        target = await acreate_user(banned_at=timezone.now())
        with self.assertRaises(ForbiddenError):
            await unban_user(target.id, user=actor)

    async def test_unban_missing_user_raises_not_found(self):
        admin = await acreate_user(is_staff=True)
        with self.assertRaises(NotFoundError):
            await unban_user("01JABCDEF0000000000000000", user=admin)
