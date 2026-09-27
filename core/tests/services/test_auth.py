from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.utils import timezone

from core.exceptions import AuthenticationException, ValidationError
from core.models import OTPChannel, OTPCode, User
from core.services.auth import auth_service
from core.tests.faker import faker
from core.tests.helpers import acreate_user, force_latest_otp_code


class AuthRegisterTestCase(TestCase):
    async def test_register_creates_new_email_user(self):
        email = faker.unique.email()

        result = await auth_service.register({"identifier": email})

        self.assertEqual(result["channel"], "email")
        user = await User.objects.aget(email=email)
        self.assertFalse(user.is_active)
        self.assertEqual(await OTPCode.objects.filter(user=user).acount(), 1)

    async def test_register_reuses_existing_user_and_issues_new_otp(self):
        email = faker.unique.email()
        await auth_service.register({"identifier": email})
        await auth_service.register({"identifier": email})

        users = [u async for u in User.objects.filter(email=email)]
        self.assertEqual(len(users), 1)
        self.assertEqual(await OTPCode.objects.filter(user=users[0]).acount(), 2)

    async def test_register_with_invalid_phone_raises(self):
        with self.assertRaises(ValidationError) as cm:
            await auth_service.register({"identifier": "not-a-phone"})
        self.assertIn("identifier", cm.exception.errors)

    async def test_register_normalises_phone_to_e164(self):
        # Pass with spaces / dashes — phonenumbers should normalise to +E.164.
        result = await auth_service.register({"identifier": "+1 415-555-2671"})
        self.assertEqual(result["channel"], "phone")
        user = await User.objects.aget(phone="+14155552671")
        self.assertTrue(user.pk)

    @patch("core.services.auth.lookup_country", new_callable=AsyncMock)
    async def test_register_passes_ip_to_geo_lookup(self, lookup_country):
        lookup_country.return_value = "FR"
        email = faker.unique.email()

        await auth_service.register({"identifier": email}, ip="9.9.9.9")

        lookup_country.assert_awaited_once_with("9.9.9.9")
        user = await User.objects.aget(email=email)
        self.assertEqual(user.country, "FR")


class AuthActivateTestCase(TestCase):
    async def test_activate_verifies_code_and_returns_tokens(self):
        email = faker.unique.email()
        await auth_service.register({"identifier": email})
        await force_latest_otp_code(await User.objects.aget(email=email))

        result = await auth_service.activate({"identifier": email, "code": "123456"})

        self.assertIn("access_token", result)
        self.assertIn("refresh_token", result)
        self.assertTrue(result["user"]["is_active"])
        user = await User.objects.aget(email=email)
        self.assertTrue(user.is_active)

    async def test_activate_wrong_code_increments_attempts(self):
        email = faker.unique.email()
        await auth_service.register({"identifier": email})

        with self.assertRaises(ValidationError):
            await auth_service.activate({"identifier": email, "code": "000000"})

        otp = await OTPCode.objects.filter(user__email=email).afirst()
        self.assertEqual(otp.attempts, 1)
        self.assertIsNone(otp.consumed_at)

    async def test_activate_expired_code_raises(self):
        email = faker.unique.email()
        await auth_service.register({"identifier": email})
        otp = await OTPCode.objects.filter(user__email=email).afirst()
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        await otp.asave(update_fields=["expires_at"])

        with self.assertRaises(ValidationError) as cm:
            await auth_service.activate({"identifier": email, "code": "000000"})
        self.assertIn("code", cm.exception.errors)

    async def test_activate_unknown_identifier_raises(self):
        with self.assertRaises(ValidationError):
            await auth_service.activate(
                {"identifier": faker.unique.email(), "code": "123456"}
            )


class AuthLoginTestCase(TestCase):
    async def test_login_with_correct_password(self):
        email = faker.unique.email()
        user = await acreate_user(email=email, password="hunter2345")

        result = await auth_service.login(
            {"identifier": email, "password": "hunter2345"}
        )

        self.assertIn("access_token", result)
        self.assertEqual(result["user"]["id"], user.id)

    async def test_login_wrong_password_raises(self):
        email = faker.unique.email()
        await acreate_user(email=email, password="hunter2345")

        with self.assertRaises(AuthenticationException) as cm:
            await auth_service.login({"identifier": email, "password": "wrong-one"})
        self.assertEqual(cm.exception.code, "invalid-credentials")

    async def test_login_inactive_user_raises(self):
        email = faker.unique.email()
        await acreate_user(email=email, password="hunter2345", is_active=False)

        with self.assertRaises(AuthenticationException):
            await auth_service.login({"identifier": email, "password": "hunter2345"})

    async def test_login_nonexistent_user_raises(self):
        with self.assertRaises(AuthenticationException):
            await auth_service.login(
                {"identifier": faker.unique.email(), "password": "hunter2345"}
            )


class AuthLoginOtpTestCase(TestCase):
    async def test_login_otp_issues_code_on_preferred_channel(self):
        email = faker.unique.email()
        user = await acreate_user(email=email, phone="+14155552681")

        result = await auth_service.login_otp({"identifier": email})

        self.assertEqual(result["channel"], OTPChannel.EMAIL)
        self.assertEqual(await OTPCode.objects.filter(user=user).acount(), 1)

    async def test_login_otp_routes_to_phone_when_preferred(self):
        email = faker.unique.email()
        user = await acreate_user(
            email=email,
            phone="+14155552682",
            parameters={"notifications": {"preferred_channel": "phone"}},
        )

        # user typed their email but prefers phone — code must go to phone
        result = await auth_service.login_otp({"identifier": email})

        self.assertEqual(result["channel"], OTPChannel.PHONE)
        otp = await OTPCode.objects.filter(user=user).afirst()
        self.assertEqual(otp.channel, OTPChannel.PHONE)

    async def test_login_otp_unknown_identifier_raises(self):
        with self.assertRaises(AuthenticationException) as cm:
            await auth_service.login_otp({"identifier": faker.unique.email()})
        self.assertEqual(cm.exception.code, "invalid-credentials")

    async def test_login_otp_inactive_user_raises(self):
        email = faker.unique.email()
        await acreate_user(email=email, is_active=False)

        with self.assertRaises(AuthenticationException):
            await auth_service.login_otp({"identifier": email})


class AuthAuthenticateTestCase(TestCase):
    async def test_authenticate_with_valid_access_token(self):
        user = await acreate_user()
        token = auth_service._create_token_pair(user)["access_token"]

        authenticated = await auth_service.authenticate(token)

        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated.id, user.id)

    async def test_authenticate_rejects_refresh_token(self):
        user = await acreate_user()
        refresh = auth_service._create_token_pair(user)["refresh_token"]

        self.assertIsNone(await auth_service.authenticate(refresh))

    async def test_authenticate_rejects_inactive_user(self):
        user = await acreate_user(is_active=False)
        token = auth_service._create_token_pair(user)["access_token"]

        self.assertIsNone(await auth_service.authenticate(token))

    async def test_authenticate_empty_token_returns_none(self):
        self.assertIsNone(await auth_service.authenticate(""))

    async def test_authenticate_malformed_token_returns_none(self):
        self.assertIsNone(await auth_service.authenticate("not.a.real.jwt"))


class AuthRefreshTestCase(TestCase):
    async def test_refresh_returns_fresh_pair_and_user(self):
        user = await acreate_user()
        refresh = auth_service._create_token_pair(user)["refresh_token"]

        result = await auth_service.refresh(refresh)

        self.assertIn("access_token", result)
        self.assertIn("refresh_token", result)
        self.assertEqual(result["user"]["id"], user.id)

    async def test_refresh_rejects_access_token(self):
        user = await acreate_user()
        access = auth_service._create_token_pair(user)["access_token"]

        with self.assertRaises(AuthenticationException):
            await auth_service.refresh(access)

    async def test_refresh_rejects_empty_token(self):
        with self.assertRaises(AuthenticationException):
            await auth_service.refresh("")

    async def test_refresh_rejects_malformed_token(self):
        with self.assertRaises(AuthenticationException):
            await auth_service.refresh("not.a.real.jwt")

    async def test_refresh_rejects_inactive_user(self):
        user = await acreate_user(is_active=False)
        refresh = auth_service._create_token_pair(user)["refresh_token"]

        with self.assertRaises(AuthenticationException):
            await auth_service.refresh(refresh)


class OTPChannelConstantsTestCase(TestCase):
    def test_constants_match_expected_values(self):
        self.assertEqual(OTPChannel.EMAIL.value, "email")
        self.assertEqual(OTPChannel.PHONE.value, "phone")
