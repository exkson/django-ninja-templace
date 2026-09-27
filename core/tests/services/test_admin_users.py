from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.exceptions import ForbiddenError, NotFoundError, ValidationError
from core.services.users import get_user, list_users
from core.tests.helpers import acreate_user


class ListUsersTestCase(TestCase):
    async def test_non_staff_is_forbidden(self):
        actor = await acreate_user(is_staff=False)
        with self.assertRaises(ForbiddenError):
            await list_users(user=actor)

    async def test_lists_everyone_newest_first(self):
        admin = await acreate_user(is_staff=True)
        older = await acreate_user(date_joined=timezone.now() - timedelta(days=2))
        newer = await acreate_user(date_joined=timezone.now() - timedelta(days=1))

        items, total = await list_users(user=admin)

        self.assertEqual(total, 3)
        self.assertEqual([u.id for u in items], [admin.id, newer.id, older.id])

    async def test_search_matches_name_email_and_phone(self):
        admin = await acreate_user(is_staff=True, first_name="Staff")
        by_name = await acreate_user(first_name="Amara")
        by_email = await acreate_user(email="amara.pro@example.com")
        by_phone = await acreate_user(email="", phone="+14155550100")

        items, _ = await list_users(search="amara", user=admin)
        self.assertEqual({u.id for u in items}, {by_name.id, by_email.id})

        items, _ = await list_users(search="5550100", user=admin)
        self.assertEqual([u.id for u in items], [by_phone.id])

    async def test_is_staff_and_is_banned_filters(self):
        admin = await acreate_user(is_staff=True)
        banned = await acreate_user(banned_at=timezone.now())
        await acreate_user()

        items, _ = await list_users(is_staff=True, user=admin)
        self.assertEqual([u.id for u in items], [admin.id])

        items, _ = await list_users(is_banned=True, user=admin)
        self.assertEqual([u.id for u in items], [banned.id])

    async def test_paginates(self):
        admin = await acreate_user(is_staff=True)
        for _ in range(4):
            await acreate_user()

        items, total = await list_users(page=2, page_size=2, user=admin)

        self.assertEqual(total, 5)
        self.assertEqual(len(items), 2)

    async def test_out_of_bounds_page_size_is_rejected(self):
        admin = await acreate_user(is_staff=True)
        with self.assertRaises(ValidationError) as cm:
            await list_users(page_size=1000, user=admin)
        self.assertIn("page_size", cm.exception.errors)


class GetUserTestCase(TestCase):
    async def test_non_staff_is_forbidden(self):
        actor = await acreate_user(is_staff=False)
        target = await acreate_user()
        with self.assertRaises(ForbiddenError):
            await get_user(target.id, user=actor)

    async def test_missing_user_raises_not_found(self):
        admin = await acreate_user(is_staff=True)
        with self.assertRaises(NotFoundError):
            await get_user("01JZZZZZZZZZZZZZZZZZZZZZZZ", user=admin)

    async def test_returns_user(self):
        admin = await acreate_user(is_staff=True)
        target = await acreate_user()

        found = await get_user(target.id, user=admin)

        self.assertEqual(found.id, target.id)
