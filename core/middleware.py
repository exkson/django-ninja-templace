from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _

from core.services.auth import auth_service


class JWTAuthMiddleware(MiddlewareMixin):
    """Resolves the Bearer token into ``request.user`` for non-public paths.

    Public path prefixes come from ``settings.JWT_PUBLIC_PATH_PREFIXES``.
    """

    async def process_view(
        self, request: HttpRequest, view_func, view_args, view_kwargs
    ):
        if not self._route_requires_auth(request):
            return None

        token = self._extract_bearer_token(request)
        user = await auth_service.authenticate(token) if token else None
        if user is None:
            return JsonResponse(
                {
                    "detail": _("Invalid or missing authentication token."),
                    "code": "invalid-token",
                },
                status=401,
            )
        if user.is_banned:
            return JsonResponse(
                {
                    "detail": _("Your account has been banned."),
                    "code": "banned-account",
                },
                status=401,
            )
        request.user = user

    @staticmethod
    def _route_requires_auth(request: HttpRequest) -> bool:
        return not any(
            request.path.startswith(prefix)
            for prefix in settings.JWT_PUBLIC_PATH_PREFIXES
        )

    @staticmethod
    def _extract_bearer_token(request: HttpRequest) -> str:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return ""
        return header.split(" ", 1)[1]
