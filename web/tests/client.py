"""End-to-end HTTP test client.

Thin wrapper around ``django.test.AsyncClient`` that makes requests traverse
the full URL configuration and Django middleware stack (including the JWT
middleware). This client is intentionally domain-agnostic — it accepts raw
Bearer tokens rather than reaching into any app's auth service to mint them.
Callers are expected to produce a token themselves (via whatever domain
service is appropriate) and hand it to :meth:`authenticate_as`.

.. code-block:: python

    from core.services.auth import auth_service
    from web.tests.client import TestClient

    tokens = auth_service._create_token_pair(user)
    client = TestClient().authenticate_as(tokens["access_token"])
    response = await client.get("/api/users/me")
    assert response.status_code == 200
"""

from typing import Any

from django.http.response import HttpResponseBase
from django.test import AsyncClient

__all__ = ["TestClient"]


class TestClient:
    def __init__(self) -> None:
        self._client = AsyncClient()
        self._headers: dict[str, str] = {}

    def authenticate_as(self, access_token: str) -> "TestClient":
        self._headers["Authorization"] = f"Bearer {access_token}"
        return self

    def unauthenticate(self) -> "TestClient":
        self._headers.pop("Authorization", None)
        return self

    def _merge_headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        if extra is None:
            return dict(self._headers)
        return {**self._headers, **extra}

    async def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        **kw: Any,
    ) -> HttpResponseBase:
        return await self._client.get(path, headers=self._merge_headers(headers), **kw)

    async def post(
        self,
        path: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
        **kw: Any,
    ) -> HttpResponseBase:
        return await self._client.post(
            path,
            data=json,
            content_type="application/json",
            headers=self._merge_headers(headers),
            **kw,
        )

    async def post_multipart(
        self,
        path: str,
        *,
        data: dict[str, Any],
        headers: dict[str, str] | None = None,
        **kw: Any,
    ) -> HttpResponseBase:
        """POST *data* as ``multipart/form-data``. File uploads go here."""
        return await self._client.post(
            path,
            data=data,
            headers=self._merge_headers(headers),
            **kw,
        )

    async def patch(
        self,
        path: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
        **kw: Any,
    ) -> HttpResponseBase:
        return await self._client.patch(
            path,
            data=json,
            content_type="application/json",
            headers=self._merge_headers(headers),
            **kw,
        )

    async def put(
        self,
        path: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
        **kw: Any,
    ) -> HttpResponseBase:
        return await self._client.put(
            path,
            data=json,
            content_type="application/json",
            headers=self._merge_headers(headers),
            **kw,
        )

    async def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        **kw: Any,
    ) -> HttpResponseBase:
        return await self._client.delete(
            path, headers=self._merge_headers(headers), **kw
        )
