from typing import Literal

import phonenumbers
from pydantic import BaseModel, field_validator

from core.exceptions import ValidationError
from core.validators import BaseValidator

Channel = Literal["email", "phone"]


def parse_identifier(raw: str) -> tuple[Channel, str]:
    """Detect whether *raw* is an email or a phone number and normalise it.

    Phone numbers must be in international E.164 format (e.g. ``+14155552671``);
    we rely on the ``phonenumbers`` library for validation.
    """
    raw = raw.strip()
    if not raw:
        raise ValidationError({"identifier": ["cannot be empty"]})

    if "@" in raw:
        return "email", raw.lower()

    try:
        parsed = phonenumbers.parse(raw, None)
    except phonenumbers.NumberParseException as e:
        raise ValidationError(
            {
                "identifier": [
                    "Invalid phone number format. "
                    "Use international format, e.g. +14155552671.",
                ]
            }
        ) from e
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError({"identifier": ["Invalid phone number."]})

    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return "phone", e164


class _RegisterV(BaseModel):
    identifier: str

    @field_validator("identifier")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("cannot be empty")
        return v


class RegisterValidator(BaseValidator[_RegisterV]):
    validation_class = _RegisterV


class _ActivateV(BaseModel):
    identifier: str
    code: str

    @field_validator("code")
    @classmethod
    def _code_shape(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("must be a 6-digit numeric code")
        return v


class ActivateValidator(BaseValidator[_ActivateV]):
    validation_class = _ActivateV


class _LoginV(BaseModel):
    identifier: str
    password: str

    @field_validator("password")
    @classmethod
    def _non_empty_password(cls, v: str) -> str:
        if not v:
            raise ValueError("cannot be empty")
        return v


class LoginValidator(BaseValidator[_LoginV]):
    validation_class = _LoginV


class _LoginOtpV(BaseModel):
    identifier: str

    @field_validator("identifier")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("cannot be empty")
        return v


class LoginOtpValidator(BaseValidator[_LoginOtpV]):
    validation_class = _LoginOtpV
