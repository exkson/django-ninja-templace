"""Shared pagination primitives.

Lives in ``core.services.pagination`` so every service that returns a
paginated list speaks the same vocabulary: same default page, same bound
checks, same wire shape. Callers compose :class:`PaginationParams` into
their pydantic validator (or feed already-validated values to
:func:`paginate` directly).

Pagination is **page-based**: ``page=1`` is the first page,
``page=N`` returns rows ``[(N-1)*page_size : N*page_size]``. ``page_size``
is bound-checked.
"""

from typing import TypeVar

from django.db.models import QuerySet
from pydantic import BaseModel, Field

LIST_PAGE_SIZE_MIN = 1
LIST_PAGE_SIZE_MAX = 100
LIST_PAGE_SIZE_DEFAULT = 20
PAGE_DEFAULT = 1

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Reusable pydantic mixin: ``page`` + ``page_size`` with bound checks.

    Inherit from this in your domain validator and add the domain-specific
    fields alongside. Failures bubble up as :class:`core.exceptions.ValidationError`
    via the standard ``BaseValidator`` machinery.
    """

    page: int = Field(default=PAGE_DEFAULT, ge=1)
    page_size: int = Field(
        default=LIST_PAGE_SIZE_DEFAULT,
        ge=LIST_PAGE_SIZE_MIN,
        le=LIST_PAGE_SIZE_MAX,
    )


async def paginate(
    queryset: QuerySet[T], *, page: int, page_size: int
) -> tuple[list[T], int]:
    """Return ``(items, total)`` slicing *queryset* by 1-indexed *page* and *page_size*.

    ``total`` is the unpaginated row count, useful for surfacing pagination
    controls in the UI. Slicing is pushed down to the ORM so only the
    page's rows are fetched.
    """
    total = await queryset.acount()
    offset = (page - 1) * page_size
    items = [item async for item in queryset[offset : offset + page_size]]
    return items, total
