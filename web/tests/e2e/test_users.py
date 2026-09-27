import json

from asgiref.sync import sync_to_async
from django.test import TestCase

from core.models import User
from core.services.auth import auth_service
from core.tests.helpers import acreate_user
from web.tests.client import TestClient


def _authed(user) -> TestClient:
    """Local helper: mint an access token for *user* and return an authed client.

    Kept inline here (rather than in web.tests.client) so the TestClient stays
    domain-agnostic — no core imports.
    """
    token = auth_service._create_token_pair(user)["access_token"]
    return TestClient().authenticate_as(token)


class GetMeE2ETestCase(TestCase):
    async def test_get_me_unauthenticated_returns_401(self):
        client = TestClient()

        response = await client.get("/api/users/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["code"], "invalid-token")

    async def test_get_me_authenticated_returns_profile(self):
        user = await acreate_user(first_name="Ada", last_name="Lovelace")
        client = _authed(user)

        response = await client.get("/api/users/me")

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["id"], user.id)
        self.assertEqual(body["email"], user.email)
        self.assertEqual(body["first_name"], "Ada")
        self.assertNotIn("internal_notes", body)

    async def test_get_me_with_bogus_token_returns_401(self):
        client = TestClient()
        client._headers["Authorization"] = "Bearer not.a.real.jwt"

        response = await client.get("/api/users/me")

        self.assertEqual(response.status_code, 401)


class PatchMeE2ETestCase(TestCase):
    async def test_patch_me_updates_names(self):
        user = await acreate_user()
        client = _authed(user)

        response = await client.patch(
            "/api/users/me",
            json={"first_name": "Ada", "last_name": "Lovelace"},
        )

        self.assertEqual(response.status_code, 200)
        refreshed = await User.objects.aget(pk=user.pk)
        self.assertEqual(refreshed.first_name, "Ada")
        self.assertEqual(refreshed.last_name, "Lovelace")

    async def test_patch_me_sets_password_then_login_works(self):
        email = "patchme-login@example.com"
        user = await acreate_user(email=email, password="original-password")
        client = _authed(user)

        patch_resp = await client.patch(
            "/api/users/me", json={"password": "brand-new-password-42"}
        )
        self.assertEqual(patch_resp.status_code, 200)

        refreshed = await User.objects.aget(pk=user.pk)
        self.assertTrue(
            await sync_to_async(refreshed.check_password)("brand-new-password-42")
        )

        # And a fresh (unauthenticated) login with the new password works.
        login_resp = await TestClient().post(
            "/api/auth/login",
            json={
                "identifier": email,
                "password": "brand-new-password-42",
            },
        )
        self.assertEqual(login_resp.status_code, 200)

    async def test_patch_me_short_password_returns_400(self):
        user = await acreate_user()
        client = _authed(user)

        response = await client.patch("/api/users/me", json={"password": "short"})

        self.assertEqual(response.status_code, 400)

    async def test_patch_me_unauthenticated_returns_401(self):
        client = TestClient()

        response = await client.patch("/api/users/me", json={"first_name": "Nope"})

        self.assertEqual(response.status_code, 401)
