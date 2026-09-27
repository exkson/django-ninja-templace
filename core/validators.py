from typing import Generic, Type, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PDValidationError

from core.exceptions import ValidationError

T = TypeVar("T", bound=BaseModel)


class BaseValidator(Generic[T]):
    validation_class: Type[T]

    @classmethod
    def validate(cls, data: dict) -> T:
        try:
            return cls.validation_class(**data)
        except PDValidationError as e:
            raise ValidationError(cls._pydantic_errors_to_dict(e.errors())) from e

    @classmethod
    def _pydantic_errors_to_dict(cls, errors: list[dict]) -> dict[str, list[str]]:
        error_dict: dict[str, list[str]] = {}
        for error in errors:
            loc = ".".join(str(i) for i in error["loc"])
            if loc not in error_dict:
                error_dict[loc] = []
            error_dict[loc].append(error["msg"])
        return error_dict
