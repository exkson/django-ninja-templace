from pydantic import AwareDatetime, BaseModel, Field

from core.services.pagination import PaginationParams
from core.validators import BaseValidator


class _PatchMeV(BaseModel):
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class PatchMeValidator(BaseValidator[_PatchMeV]):
    validation_class = _PatchMeV


class _ListUsersV(PaginationParams):
    search: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=2)
    is_staff: bool | None = None
    is_banned: bool | None = None
    joined_after: AwareDatetime | None = None
    joined_before: AwareDatetime | None = None


class ListUsersValidator(BaseValidator[_ListUsersV]):
    validation_class = _ListUsersV
