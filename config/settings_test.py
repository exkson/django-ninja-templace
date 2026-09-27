"""Settings overrides for the test suite.

Imports the regular settings as a base, then pins every I/O-bound backend to
an in-process fake so tests can't reach the network through whatever
provider/transport the developer's env points at.

Activated by ``scripts/test.sh``, which exports
``DJANGO_SETTINGS_MODULE=config.settings_test`` before invoking the test
runner. Direct ``manage.py test`` invocations should pass
``--settings=config.settings_test`` (or set the env var manually) to get
the same isolation.
"""

import logging

from config.settings import *  # noqa: F401, F403

# --- Logging ---
# Rotating-file and console handlers are pure noise during tests (and needless
# disk writes), so replace the config with a no-handler one and switch logging
# off entirely.
LOGGING = {"version": 1, "disable_existing_loggers": False}
logging.disable(logging.CRITICAL)

# --- Password hashing ---
# Production hashers dominate test time because the suite creates users and
# logs in constantly. MD5 is insecure but fine for tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# --- JWT ---
JWT_SECRET_KEY = "test-jwt-secret-that-is-long-enough-for-hmac-sha256"

# --- WhatsApp ---
# Console fake: writes to logs instead of dialing a real provider.
WHATSAPP_BACKEND = "core.services.whatsapp.ConsoleWhatsAppClient"

# --- Email ---
# In-memory backend; ``django.core.mail.outbox`` collects messages so tests can
# assert on email content while SMTP sockets are never opened.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# --- Geo IP ---
# Invalid host: ``core.services.geo.lookup_country`` catches HTTPError and
# returns the default country code, so a lookup with a non-private IP becomes
# a no-op instead of a real DNS round-trip.
GEO_IP_PROVIDER_URL = "http://geo.test.invalid/{ip}/"

# --- Uploads ---
# Keep test uploads under /tmp so the dev media tree isn't clobbered.
MEDIA_ROOT = "/tmp/app-tests-media"
