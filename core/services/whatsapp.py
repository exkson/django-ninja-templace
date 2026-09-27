"""Pluggable WhatsApp client for delivering OTPs.

The actual provider (Twilio, Meta WhatsApp Cloud API, a local aggregator,
…) is chosen per deployment. Select an implementation through the
``WHATSAPP_BACKEND`` env var — it's a dotted import path to a class with
an ``async def send(phone: str, message: str) -> None`` method.

``ConsoleWhatsAppClient`` is the default: it logs the message at warning level
so the end-to-end flow is usable locally without external credentials (the
message lands in ``services.log``, and on the console when ``DEBUG`` is on).
Replace before going to production.
"""

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class WhatsAppClient(Protocol):
    async def send(self, phone: str, message: str) -> None: ...


class ConsoleWhatsAppClient:
    async def send(self, phone: str, message: str) -> None:
        logger.warning("[WHATSAPP STUB] to=%s: %s", phone, message)
