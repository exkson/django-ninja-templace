"""IP → ISO country-code lookup.

Default implementation hits ``https://ipapi.co/{ip}/country/`` (no key, 1 000
req/day free tier). Failures are swallowed — registration must never block on
geocoding. Swap the provider or cache via env var ``GEO_IP_PROVIDER_URL``,
or rewrite this service with a production-grade solution (MaxMind GeoLite2, a
paid API, …).

This module intentionally takes primitives (a string IP). Extracting the
client IP from an ``HttpRequest`` is a web-layer concern and lives in the
caller (see ``web/views/auth.py``).
"""

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_PRIVATE_PREFIXES = (
    "127.",
    "10.",
    "192.168.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
)


async def lookup_country(ip: str) -> str:
    """Return the ISO 3166-1 alpha-2 country of *ip*, or ``settings.DEFAULT_COUNTRY``."""
    default = settings.DEFAULT_COUNTRY
    if not ip or ip.startswith(_PRIVATE_PREFIXES):
        return default
    url = settings.GEO_IP_PROVIDER_URL.format(ip=ip)
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            country = response.text.strip()
            if len(country) == 2 and country.isalpha():
                return country.upper()
            return default
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Geo lookup failed for %s: %s", ip, exc)
        return default
