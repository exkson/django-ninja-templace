import json
from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.utils import timezone

from core.models import User
from core.services.auth import auth_service
from core.tests.helpers import acreate_user
from web.tests.client import TestClient

NOTIFY_BANNED = "core.services.notifications.notification_manager.send_account_banned"


def _authed(user) -> TestClient:
    token = auth_service._create_token_pair(user)["access_token"]
    return TestClient().authenticate_as(token)


class BanEndpointE2ETestCase(TestCase):
    @patch(NOTIFY_BANNED, new_callable=AsyncMock)
    async def test_staff_can_ban_user(self, _notify):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user()

        response = await _authed(admin).post(
            f"/api/admin/users/{target.id}/ban",
            json={"reason": "abuse"},
        )

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body["is_banned"])
        self.assertEqual(body["ban_reason"], "abuse")
        refreshed = await User.objects.aget(pk=target.pk)
        self.assertIsNotNone(refreshed.banned_at)

    async def test_non_staff_cannot_ban_user(self):
        actor = await acreate_user(is_staff=False)
        target = await acreate_user()

        response = await _authed(actor).post(
            f"/api/admin/users/{target.id}/ban",
            json={"reason": "abuse"},
        )

        self.assertEqual(response.status_code, 403)
        refreshed = await User.objects.aget(pk=target.pk)
        self.assertIsNone(refreshed.banned_at)

    async def test_unauthenticated_ban_is_rejected(self):
        target = await acreate_user()

        response = await TestClient().post(
            f"/api/admin/users/{target.id}/ban",
            json={"reason": "abuse"},
        )

        self.assertEqual(response.status_code, 401)


class BannedUserAccessE2ETestCase(TestCase):
    @patch(NOTIFY_BANNED, new_callable=AsyncMock)
    async def test_banned_user_token_is_rejected(self, _notify):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user()
        target_client = _authed(target)

        # Sanity: access works before the ban.
        self.assertEqual((await target_client.get("/api/users/me")).status_code, 200)

        await _authed(admin).post(
            f"/api/admin/users/{target.id}/ban", json={"reason": "abuse"}
        )

        response = await target_client.get("/api/users/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["code"], "banned-account")

    @patch(NOTIFY_BANNED, new_callable=AsyncMock)
    async def test_unban_restores_access(self, _notify):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user()
        target_client = _authed(target)

        await _authed(admin).post(
            f"/api/admin/users/{target.id}/ban", json={"reason": "abuse"}
        )
        self.assertEqual((await target_client.get("/api/users/me")).status_code, 401)

        unban = await _authed(admin).post(f"/api/admin/users/{target.id}/unban")
        self.assertEqual(unban.status_code, 200)
        self.assertFalse(json.loads(unban.content)["is_banned"])

        self.assertEqual((await target_client.get("/api/users/me")).status_code, 200)


class AdminUserListE2ETestCase(TestCase):
    async def test_staff_lists_users(self):
        admin = await acreate_user(is_staff=True)
        admin.last_login = timezone.now()
        await admin.asave(update_fields=["last_login"])
        await acreate_user(first_name="Amara")

        response = await _authed(admin).get("/api/admin/users?search=Amara")

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["page"], 1)
        row = body["items"][0]
        self.assertEqual(row["first_name"], "Amara")
        self.assertIn("joined_at", row)
        self.assertIsNone(row["last_login"])
        self.assertFalse(row["is_banned"])

    async def test_filter_staff_only(self):
        admin = await acreate_user(is_staff=True)
        await acreate_user()

        response = await _authed(admin).get("/api/admin/users?is_staff=true")

        body = json.loads(response.content)
        self.assertEqual([row["id"] for row in body["items"]], [admin.id])

    async def test_non_staff_cannot_list_users(self):
        actor = await acreate_user(is_staff=False)
        response = await _authed(actor).get("/api/admin/users")
        self.assertEqual(response.status_code, 403)

    async def test_unauthenticated_list_is_rejected(self):
        response = await TestClient().get("/api/admin/users")
        self.assertEqual(response.status_code, 401)

    async def test_out_of_bounds_page_size_returns_400(self):
        admin = await acreate_user(is_staff=True)
        response = await _authed(admin).get("/api/admin/users?page_size=1000")
        self.assertEqual(response.status_code, 400)
        self.assertIn("page_size", json.loads(response.content))


class AdminUserDetailE2ETestCase(TestCase):
    async def test_staff_fetches_user_detail(self):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user(country="FR")

        response = await _authed(admin).get(f"/api/admin/users/{target.id}")

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["id"], target.id)
        self.assertEqual(body["country"], "FR")

    async def test_non_staff_cannot_fetch_detail(self):
        actor = await acreate_user(is_staff=False)
        target = await acreate_user()
        response = await _authed(actor).get(f"/api/admin/users/{target.id}")
        self.assertEqual(response.status_code, 403)

    async def test_missing_user_returns_404(self):
        admin = await acreate_user(is_staff=True)
        response = await _authed(admin).get(
            "/api/admin/users/01JZZZZZZZZZZZZZZZZZZZZZZZ"
        )
        self.assertEqual(response.status_code, 404)
