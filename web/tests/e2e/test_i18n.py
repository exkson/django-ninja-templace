import json

from django.test import TestCase

from core.tests.faker import faker
from web.tests.client import TestClient


class LocaleNegotiationE2ETestCase(TestCase):
    async def test_error_messages_follow_accept_language(self):
        payload = {"identifier": faker.unique.email(), "password": "whatever-123"}

        english = await TestClient().post("/api/auth/login", json=payload)
        french = await TestClient().post(
            "/api/auth/login", json=payload, headers={"Accept-Language": "fr"}
        )

        self.assertEqual(json.loads(english.content)["detail"], "Invalid credentials")
        self.assertEqual(json.loads(french.content)["detail"], "Identifiants invalides")
