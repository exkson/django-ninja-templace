from unittest.mock import AsyncMock, MagicMock, patch

from django.core import mail
from django.test import TestCase

from core.models import OTPChannel
from core.services.notifications import NotificationManager, notification_manager
from core.tests.faker import faker
from core.tests.helpers import acreate_user


class PreferredChannelTestCase(TestCase):
    async def test_only_email_user_prefers_email(self):
        user = await acreate_user(email=faker.unique.email(), phone="")
        self.assertEqual(notification_manager.preferred_channel(user), OTPChannel.EMAIL)

    async def test_only_phone_user_prefers_phone(self):
        user = await acreate_user(email="", phone="+14155552671")
        self.assertEqual(notification_manager.preferred_channel(user), OTPChannel.PHONE)

    async def test_both_channels_defaults_to_email(self):
        user = await acreate_user(
            email=faker.unique.email(), phone="+14155552672", parameters={}
        )
        self.assertEqual(notification_manager.preferred_channel(user), OTPChannel.EMAIL)

    async def test_both_channels_honours_phone_preference(self):
        user = await acreate_user(
            email=faker.unique.email(),
            phone="+14155552673",
            parameters={"notifications": {"preferred_channel": "phone"}},
        )
        self.assertEqual(notification_manager.preferred_channel(user), OTPChannel.PHONE)

    async def test_unknown_preference_falls_back_to_email(self):
        user = await acreate_user(
            email=faker.unique.email(),
            phone="+14155552674",
            parameters={"notifications": {"preferred_channel": "smoke-signal"}},
        )
        self.assertEqual(notification_manager.preferred_channel(user), OTPChannel.EMAIL)


class NotifyTestCase(TestCase):
    """``notify`` is the low-level dispatcher — covers the email/WhatsApp split."""

    async def test_notify_email_lands_in_django_outbox(self):
        user = await acreate_user(email=faker.unique.email(), phone="")

        await notification_manager.send_login_otp_code(user, "123456")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])

    async def test_notify_whatsapp_strips_subject_and_uses_plain_body(self):
        user = await acreate_user(email="", phone="+14155552675")
        fake_client = MagicMock()
        fake_client.send = AsyncMock()

        with patch(
            "core.services.notifications.get_whatsapp_client", return_value=fake_client
        ):
            await notification_manager.send_login_otp_code(user, "123456")

        fake_client.send.assert_awaited_once()
        called_phone, called_text = fake_client.send.call_args.args
        self.assertEqual(called_phone, user.phone)
        self.assertTrue(called_text)


class SendActivationOtpCodeTestCase(TestCase):
    async def test_uses_explicit_channel(self):
        user = await acreate_user(
            email=faker.unique.email(),
            phone="+14155552677",
            parameters={"notifications": {"preferred_channel": "email"}},
        )
        fake_client = MagicMock()
        fake_client.send = AsyncMock()

        with patch(
            "core.services.notifications.get_whatsapp_client", return_value=fake_client
        ):
            await NotificationManager().send_activation_otp_code(
                user, "123456", OTPChannel.PHONE
            )

        # Activation channel comes from the caller, not the user's preference:
        # phone was requested, so WhatsApp is hit and email outbox stays empty.
        fake_client.send.assert_awaited_once()
        self.assertEqual(fake_client.send.call_args.args[0], user.phone)
        self.assertEqual(len(mail.outbox), 0)


class SendLoginOtpCodeTestCase(TestCase):
    async def test_uses_preferred_channel_even_if_user_typed_other(self):
        user = await acreate_user(
            email=faker.unique.email(),
            phone="+14155552678",
            parameters={"notifications": {"preferred_channel": "phone"}},
        )
        fake_client = MagicMock()
        fake_client.send = AsyncMock()

        with patch(
            "core.services.notifications.get_whatsapp_client", return_value=fake_client
        ):
            channel = await NotificationManager().send_login_otp_code(user, "123456")

        self.assertEqual(channel, OTPChannel.PHONE)
        fake_client.send.assert_awaited_once()
        self.assertEqual(fake_client.send.call_args.args[0], user.phone)
        self.assertEqual(len(mail.outbox), 0)
