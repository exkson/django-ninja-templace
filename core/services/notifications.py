"""Notification delivery.

Separation of concerns:
  * Templates own the wording (``core/templates/templated_email/*.email``).
  * Per-event methods on ``NotificationManager`` (``send_activation_otp_code``,
    ``send_login_otp_code``, ``send_account_banned``, …) own the mapping
    between a business event and a template + channel-selection policy.
  * ``NotificationManager.notify`` is the low-level dispatcher: given a user,
    a channel and an already-built message, push it through the right
    transport. Callers in other services MUST go through the per-event
    methods, never call ``notify`` directly.

Adding an event: create ``core/templates/templated_email/<name>.email`` with
``subject`` / ``plain`` / ``html`` blocks, then add a ``send_<event>`` method
that renders it and calls ``notify`` (registered user) or ``_notify_raw``
(bare email/phone identifier with no account yet).
"""

import importlib
import logging
import smtplib

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from templated_email import get_templated_mail

from core.models import OTPChannel, User
from core.services.whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)


whatsapp_client: WhatsAppClient | None = None


def _load_whatsapp_client() -> WhatsAppClient:
    dotted = settings.WHATSAPP_BACKEND
    module_path, class_name = dotted.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls()


def get_whatsapp_client() -> WhatsAppClient:
    if whatsapp_client is None:
        return _load_whatsapp_client()
    return whatsapp_client


def _render(template_name: str, context: dict) -> EmailMultiAlternatives:
    """Render a ``.email`` template into an unsent ``EmailMultiAlternatives``.

    ``app_name`` is injected into every template context. The ``to`` list is
    left as a placeholder; the dispatcher overwrites it.
    """
    return get_templated_mail(
        template_name=template_name,
        from_email=None,
        to=[""],
        context={"app_name": settings.APP_NAME, **context},
    )


def _obfuscate(secret: str) -> str:
    return (
        "***" if len(secret) <= 2 else secret[0] + "*" * (len(secret) - 2) + secret[-1]
    )


class NotificationManager:
    """Per-event notification API. Picks template, picks channel, dispatches."""

    def preferred_channel(self, user: User) -> str:
        """Pick the channel a user should be reached on.

        Policy:
          * only email set → email
          * only phone set → phone (WhatsApp)
          * both set → ``user.parameters["notifications"]["preferred_channel"]``,
            defaulting to email because SMTP is free while messaging APIs
            are metered.
        """
        if not user.phone:
            return OTPChannel.EMAIL
        if not user.email:
            return OTPChannel.PHONE
        pref = (user.parameters or {}).get("notifications", {}).get("preferred_channel")
        if pref in (OTPChannel.EMAIL, OTPChannel.PHONE):
            return pref
        return OTPChannel.EMAIL

    async def notify(
        self,
        user: User,
        channel: str,
        subject: str,
        message: EmailMultiAlternatives | str,
        cc: list[str] | None = None,
    ) -> None:
        """Deliver an already-built *message* to *user* on *channel*.

        Internal dispatcher — callers should use the per-event methods below.
        For email, *message* may be an ``EmailMultiAlternatives`` (rendered
        from a template) or a plain string (used as the body); *subject* is
        applied either way. *cc* adds carbon-copy recipients (email only).
        For WhatsApp, only the plain part is used and *subject* and *cc* are
        ignored.

        Delivery failures are logged and swallowed: notification crashes
        must not break the business flow that triggered them.
        """
        address = user.email if channel == OTPChannel.EMAIL else user.phone
        await self._dispatch(
            channel=channel,
            address=address,
            subject=subject,
            message=message,
            user_label=str(user.pk),
            cc=cc,
        )

    async def send_activation_otp_code(
        self, user: User, code: str, channel: str
    ) -> None:
        """OTP for the register/activate flow. Channel is dictated by the
        identifier the user typed, not by their preferences."""
        msg = _render("otp", {"code": code})
        await self.notify(user, channel, msg.subject, msg)

    async def send_login_otp_code(self, user: User, code: str) -> str:
        """OTP for the OTP-login flow. Always goes to the preferred channel,
        even if the user typed their non-preferred identifier. Returns the
        channel actually used."""
        channel = self.preferred_channel(user)
        msg = _render("otp", {"code": code})
        await self.notify(user, channel, msg.subject, msg)
        return channel

    async def send_account_banned(self, user: User, reason: str) -> str:
        """Account banned by staff. Returns the channel used."""
        channel = self.preferred_channel(user)
        msg = _render("account_banned", {"user": user, "reason": reason})
        await self.notify(user, channel, msg.subject, msg)
        return channel

    async def _notify_raw(
        self,
        identifier: str,
        channel: str,
        subject: str,
        message: EmailMultiAlternatives | str,
    ) -> None:
        """Deliver *message* to a raw email/phone *identifier*, without a User.

        Mirrors :meth:`notify`'s dispatch shape but doesn't require a
        registered user (e.g. inviting someone to sign up). Failures are
        logged and swallowed.
        """
        await self._dispatch(
            channel=channel,
            address=identifier,
            subject=subject,
            message=message,
            user_label="<unregistered>",
        )

    async def _dispatch(
        self,
        *,
        channel: str,
        address: str,
        subject: str,
        message: EmailMultiAlternatives | str,
        user_label: str,
        cc: list[str] | None = None,
    ) -> None:
        """Send *message* to *address* on *channel*; swallow + log delivery failures.

        *user_label* is what appears in the log line — a User pk for
        ``notify``, ``"<unregistered>"`` for ``_notify_raw``. *cc* applies to
        email only.
        """
        try:
            if channel == OTPChannel.EMAIL:
                if isinstance(message, EmailMultiAlternatives):
                    email = message
                    email.subject = subject
                    email.to = [address]
                    email.cc = cc or []
                else:
                    email = EmailMessage(
                        subject=subject, body=message, to=[address], cc=cc or []
                    )
                await sync_to_async(email.send)()
                logger.info(
                    "notification sent: channel=email user=%s to=%s subject=%r",
                    user_label,
                    address,
                    subject,
                )
            else:
                text = (
                    message.body
                    if isinstance(message, EmailMultiAlternatives)
                    else message
                )
                await get_whatsapp_client().send(address, text.strip())
                logger.info(
                    "notification sent: channel=whatsapp user=%s to=%s",
                    user_label,
                    address,
                )
        except smtplib.SMTPAuthenticationError:
            logger.error(
                "SMTP auth error: check your credentials and security settings. "
                "username=%s password=%s",
                settings.EMAIL_HOST_USER,
                _obfuscate(settings.EMAIL_HOST_PASSWORD),
            )
        except Exception:
            logger.exception(
                "notification failed: channel=%s user=%s subject=%r",
                channel,
                user_label,
                subject,
            )


notification_manager = NotificationManager()
