from ninja import Schema
from pydantic import RootModel

from core.exceptions import AuthExceptionCode


class PaginatedResponse[T](Schema):
    """Wire shape for any paginated list endpoint.

    Subclass with the concrete item type to define a list response::

        class TransactionListResponse(PaginatedResponse[TransactionResponse]):
            pass

    The ``page`` / ``page_size`` contract matches the request side
    (:mod:`core.services.pagination`'s ``PaginationParams``) — same name on
    the URL, in the validator, and in the response.
    """

    items: list[T]
    total: int
    page: int
    page_size: int


class AuthErrorResponse(Schema):
    detail: str = "Authentication credentials were not provided."
    code: AuthExceptionCode = "invalid-credentials"


class ForbiddenErrorResponse(Schema):
    detail: str = "You do not have permission to perform this action."


class NotFoundErrorResponse(Schema):
    detail: str = "Resource not found."


class ValidationErrorResponse(RootModel[dict[str, list[str]]]):
    """Flat ``{field: [messages]}`` mapping returned by the ValidationError handler.

    Keys are field names from the submitted payload; values are the list of
    error messages for that field. The reserved key ``"detail"`` is used when
    the error is not tied to a specific field but to the whole model state
    (cross-field invariants, guards on existing records, etc.).

    Examples:
        {"first_name": ["cannot be empty"], "birthdate": ["must be at least 18 years old"]}
        {"detail": ["Account is already active."]}
    """


class UserBrief(Schema):
    id: str
    email: str
    phone: str
    first_name: str
    last_name: str
    country: str
    is_active: bool
    is_staff: bool
    is_superuser: bool
