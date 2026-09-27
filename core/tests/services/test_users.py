from asgiref.sync import sync_to_async
from django.test import TestCase

from core.models import User
from core.services.users import me_payload, patch_me
from core.tests.faker import faker
from core.tests.helpers import acreate_user


class MePayloadTestCase(TestCase):
    async def test_me_payload_shape(self):
        user = await acreate_user(
            email=faker.unique.email(),
            first_name="Ada",
            last_name="Lovelace",
            country="FR",
        )

        payload = me_payload(user)

        self.assertEqual(payload["id"], user.id)
        self.assertEqual(payload["email"], user.email)
        self.assertEqual(payload["first_name"], "Ada")
        self.assertEqual(payload["last_name"], "Lovelace")
        self.assertEqual(payload["country"], "FR")
        self.assertTrue(payload["is_active"])
        # Sensitive/admin-only fields must NOT leak.
        self.assertNotIn("internal_notes", payload)
        self.assertNotIn("password", payload)


class PatchMeTestCase(TestCase):
    async def test_patch_me_updates_names(self):
        user = await acreate_user()

        result = await patch_me(
            {"first_name": "Ada", "last_name": "Lovelace"}, user=user
        )

        self.assertEqual(result["first_name"], "Ada")
        self.assertEqual(result["last_name"], "Lovelace")
        refreshed = await User.objects.aget(pk=user.pk)
        self.assertEqual(refreshed.first_name, "Ada")
        self.assertEqual(refreshed.last_name, "Lovelace")

    async def test_patch_me_sets_password(self):
        user = await acreate_user(password="original-password")

        await patch_me({"password": "brand-new-password"}, user=user)

        refreshed = await User.objects.aget(pk=user.pk)
        self.assertTrue(
            await sync_to_async(refreshed.check_password)("brand-new-password")
        )
        self.assertFalse(
            await sync_to_async(refreshed.check_password)("original-password")
        )

    async def test_patch_me_partial_update_leaves_other_fields_alone(self):
        user = await acreate_user(first_name="Keep", last_name="Me")

        await patch_me({"first_name": "Changed"}, user=user)

        refreshed = await User.objects.aget(pk=user.pk)
        self.assertEqual(refreshed.first_name, "Changed")
        self.assertEqual(refreshed.last_name, "Me")
