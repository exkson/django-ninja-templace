import json

from django.test import TestCase

from core.models import OTPCode, User
from core.services.auth import auth_service
from core.tests.faker import faker
from core.tests.helpers import acreate_user, force_latest_otp_code
from web.tests.client import TestClient


class RegisterE2ETestCase(TestCase):
    async def test_register_with_email_returns_200(self):
        client = TestClient()
        email = faker.unique.email()

        response = await client.post("/api/auth/register", json={"identifier": email})

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["channel"], "email")
        self.assertIn("expires_at", body)
        self.assertTrue(await User.objects.filter(email=email).aexists())

    async def test_register_with_invalid_phone_returns_400(self):
        client = TestClient()

        response = await client.post(
            "/api/auth/register", json={"identifier": "not-a-phone"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("identifier", json.loads(response.content))

    async def test_register_with_phone_uses_whatsapp(self):
        client = TestClient()

        response = await client.post(
            "/api/auth/register", json={"identifier": "+14155552671"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["channel"], "phone")


class ActivateE2ETestCase(TestCase):
    async def test_activate_happy_path(self):
        client = TestClient()
        email = faker.unique.email()
        await client.post("/api/auth/register", json={"identifier": email})
        await force_latest_otp_code(await User.objects.aget(email=email))

        response = await client.post(
            "/api/auth/activate",
            json={"identifier": email, "code": "123456"},
        )

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        self.assertTrue(body["user"]["is_active"])

    async def test_activate_wrong_code_returns_400(self):
        client = TestClient()
        email = faker.unique.email()
        await client.post("/api/auth/register", json={"identifier": email})

        response = await client.post(
            "/api/auth/activate",
            json={"identifier": email, "code": "000000"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", json.loads(response.content))

    async def test_activate_malformed_code_returns_400(self):
        client = TestClient()
        response = await client.post(
            "/api/auth/activate",
            json={"identifier": faker.unique.email(), "code": "not-digits"},
        )
        self.assertEqual(response.status_code, 400)


class LoginE2ETestCase(TestCase):
    async def test_login_with_correct_password(self):
        client = TestClient()
        email = faker.unique.email()
        await acreate_user(email=email, password="hunter2345")

        response = await client.post(
            "/api/auth/login",
            json={"identifier": email, "password": "hunter2345"},
        )

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertIn("access_token", body)

    async def test_login_wrong_password_returns_401(self):
        client = TestClient()
        email = faker.unique.email()
        await acreate_user(email=email, password="hunter2345")

        response = await client.post(
            "/api/auth/login",
            json={"identifier": email, "password": "wrong"},
        )

        self.assertEqual(response.status_code, 401)
        body = json.loads(response.content)
        self.assertEqual(body["code"], "invalid-credentials")


class LoginOtpE2ETestCase(TestCase):
    async def test_login_otp_sends_email_for_email_only_user(self):
        client = TestClient()
        email = faker.unique.email()
        await acreate_user(email=email)

        response = await client.post("/api/auth/login/otp", json={"identifier": email})

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body["channel"], "email")
        self.assertIn("expires_at", body)
        self.assertTrue(await OTPCode.objects.filter(user__email=email).aexists())

    async def test_login_otp_respects_phone_preference(self):
        client = TestClient()
        email = faker.unique.email()
        await acreate_user(
            email=email,
            phone="+14155552690",
            parameters={"notifications": {"preferred_channel": "phone"}},
        )

        response = await client.post("/api/auth/login/otp", json={"identifier": email})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["channel"], "phone")

    async def test_login_otp_unknown_identifier_returns_401(self):
        client = TestClient()
        response = await client.post(
            "/api/auth/login/otp", json={"identifier": faker.unique.email()}
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["code"], "invalid-credentials")


class RefreshE2ETestCase(TestCase):
    async def test_refresh_returns_new_token_pair(self):
        client = TestClient()
        user = await acreate_user()
        tokens = auth_service._create_token_pair(user)

        response = await client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        self.assertEqual(body["user"]["id"], user.id)

    async def test_refresh_with_malformed_token_returns_401(self):
        client = TestClient()

        response = await client.post(
            "/api/auth/refresh", json={"refresh_token": "not-a-jwt"}
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["code"], "invalid-token")

    async def test_refresh_rejects_access_token(self):
        client = TestClient()
        user = await acreate_user()
        tokens = auth_service._create_token_pair(user)

        response = await client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["access_token"]}
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["code"], "invalid-token")

    async def test_refresh_rejects_inactive_user(self):
        client = TestClient()
        user = await acreate_user(is_active=False)
        tokens = auth_service._create_token_pair(user)

        response = await client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)["code"], "invalid-token")
