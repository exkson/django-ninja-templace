from typing import Literal

from django.utils.translation import gettext_lazy as _

AuthExceptionCode = Literal[
    "invalid-credentials",
    "invalid-refresh-token",
    "refresh-token-expired",
    "invalid-token",
    "banned-account",
]


class ForbiddenError(Exception):
    def __init__(
        self, message: str = _("You're not allowed to perform this action."), *args
    ):
        super().__init__(*args)
        self.message = message


class NotFoundError(Exception):
    """Raised when a resource is missing OR the caller is not allowed to see it.

    Conflating "missing" and "forbidden" here is deliberate: it avoids leaking
    the existence of resources to users who shouldn't know about them.
    """

    def __init__(self, message: str = _("Resource not found."), *args):
        super().__init__(*args)
        self.message = message


class ValidationError(Exception):
    def __init__(self, errors: dict[str, list[str]] | str):
        self.errors = {"detail": [errors]} if isinstance(errors, str) else errors

    def json(self) -> dict[str, list[str]]:
        return self.errors


class AuthenticationException(Exception):
    def __init__(self, message: str, code: AuthExceptionCode):
        self.message = message
        self.code = code
        super().__init__(message)
