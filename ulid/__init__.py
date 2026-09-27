from __future__ import annotations

import functools
import os
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Generic, Self, TypeVar

from . import base32, constants

T = TypeVar("T", bound=type)
R = TypeVar("R")


class validate_type(Generic[T]):  # noqa: N801
    def __init__(self, *types: T) -> None:
        self.types = types

    def __call__(self, func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapped(cls: Any, value: T) -> R:
            if not isinstance(value, self.types):
                message = "Value has to be of type "
                message += " or ".join([t.__name__ for t in self.types])
                raise TypeError(message)
            return func(cls, value)

        return wrapped


class ValueProvider:
    def __init__(self) -> None:
        self.lock = Lock()
        self.prev_timestamp = constants.MIN_TIMESTAMP
        self.prev_randomness = constants.MIN_RANDOMNESS

    def timestamp(self, value: float | None = None) -> int:
        if value is None:
            value = time.time_ns() // constants.NANOSECS_IN_MILLISECS
        elif isinstance(value, float):
            value = int(value * constants.MILLISECS_IN_SECS)
        if value > constants.MAX_TIMESTAMP:
            raise ValueError("Value exceeds maximum possible timestamp")
        return value

    def randomness(self) -> bytes:
        with self.lock:
            current_timestamp = self.timestamp()
            if current_timestamp == self.prev_timestamp:
                if self.prev_randomness == constants.MAX_RANDOMNESS:
                    raise ValueError("Randomness within same millisecond exhausted")
                randomness = self.increment_bytes(self.prev_randomness)
            else:
                randomness = os.urandom(constants.RANDOMNESS_LEN)

            self.prev_randomness = randomness
            self.prev_timestamp = current_timestamp
        return randomness

    def increment_bytes(self, value: bytes) -> bytes:
        length = len(value)
        return (int.from_bytes(value, byteorder="big") + 1).to_bytes(
            length, byteorder="big"
        )


@functools.total_ordering
class ULID:
    provider = ValueProvider()

    """The :class:`ULID` object consists of a timestamp part of 48 bits and of 80 random bits.

    .. code-block:: text

       01AN4Z07BY      79KA1307SR9X4MV3
      |----------|    |----------------|
       Timestamp          Randomness
         48bits             80bits

    You usually create a new :class:`ULID`-object by calling the default constructor with no
    arguments. In that case it will fill the timestamp part with the current datetime. To encode the
    object you usually convert it to a string:

        >>> ulid = ULID()
        >>> str(ulid)
        '01E75PVKXA3GFABX1M1J9NZZNF'

    Args:
        value (bytes, None):  A sequence of 16 bytes representing an encoded ULID.

    Raises:
        ValueError: If the provided value is not a valid encoded ULID.
    """

    def __init__(self, value: bytes | None = None) -> None:
        if value is not None and len(value) != constants.BYTES_LEN:
            raise ValueError("ULID has to be exactly 16 bytes long.")
        self.bytes: bytes = (
            value or ULID.from_timestamp(self.provider.timestamp()).bytes
        )

    @classmethod
    def as_str(cls) -> str:
        """Generate a new ULID and return it as a string."""
        return str(cls())

    @classmethod
    @validate_type(datetime)
    def from_datetime(cls, value: datetime) -> Self:
        """Create a new :class:`ULID`-object from a :class:`datetime`. The timestamp part of the
        `ULID` will be set to the corresponding timestamp of the datetime.

        Examples:

            >>> from datetime import datetime
            >>> ULID.from_datetime(datetime.now())
            ULID(01E75QRYCAMM1MKQ9NYMYT6SAV)
        """
        return cls.from_timestamp(value.timestamp())

    @classmethod
    @validate_type(int, float)
    def from_timestamp(cls, value: float) -> Self:
        """Create a new :class:`ULID`-object from a timestamp. The timestamp can be either a
        `float` representing the time in seconds (as it would be returned by :func:`time.time()`)
        or an `int` in milliseconds.

        Examples:

            >>> import time
            >>> ULID.from_timestamp(time.time())
            ULID(01E75QWN5HKQ0JAVX9FG1K4YP4)
        """
        timestamp = int.to_bytes(
            cls.provider.timestamp(value), constants.TIMESTAMP_LEN, "big"
        )
        randomness = cls.provider.randomness()
        return cls.from_bytes(timestamp + randomness)

    @classmethod
    @validate_type(uuid.UUID)
    def from_uuid(cls, value: uuid.UUID) -> Self:
        """Create a new :class:`ULID`-object from a :class:`uuid.UUID`. The timestamp part will be
        random in that case.

        Examples:

            >>> from uuid import uuid4
            >>> ULID.from_uuid(uuid4())
            ULID(27Q506DP7E9YNRXA0XVD8Z5YSG)
        """
        return cls(value.bytes)

    @classmethod
    @validate_type(bytes)
    def from_bytes(cls, bytes_: bytes) -> Self:
        """Create a new :class:`ULID`-object from sequence of 16 bytes."""
        return cls(bytes_)

    @classmethod
    @validate_type(str)
    def from_hex(cls, value: str) -> Self:
        """Create a new :class:`ULID`-object from 32 character string of hex values."""
        return cls.from_bytes(bytes.fromhex(value))

    @classmethod
    @validate_type(str)
    def from_str(cls, string: str) -> Self:
        """Create a new :class:`ULID`-object from a 26 char long string representation."""
        return cls(base32.decode(string))

    @classmethod
    @validate_type(int)
    def from_int(cls, value: int) -> Self:
        """Create a new :class:`ULID`-object from an `int`."""
        return cls(int.to_bytes(value, constants.BYTES_LEN, "big"))

    @functools.cached_property
    def milliseconds(self) -> int:
        """The timestamp part as epoch time in milliseconds.

        Examples:

            >>> ulid.milliseconds
            1588257207560
        """
        return int.from_bytes(self.bytes[: constants.TIMESTAMP_LEN], byteorder="big")

    @functools.cached_property
    def timestamp(self) -> float:
        """The timestamp part as epoch time in seconds.

        Examples:

            >>> ulid.timestamp
            1588257207.56
        """
        return self.milliseconds / constants.MILLISECS_IN_SECS

    @functools.cached_property
    def datetime(self) -> datetime:
        """Return the timestamp part as timezone-aware :class:`datetime` in UTC.

        Examples:

            >>> ulid.datetime
            datetime.datetime(2020, 4, 30, 14, 33, 27, 560000, tzinfo=datetime.timezone.utc)
        """
        return datetime.fromtimestamp(self.timestamp, timezone.utc)

    @functools.cached_property
    def hex(self) -> str:
        """Encode the :class:`ULID`-object as a 32 char sequence of hex values."""
        return self.bytes.hex()

    def to_uuid(self) -> uuid.UUID:
        """Convert the :class:`ULID` to a :class:`uuid.UUID`."""
        return uuid.UUID(bytes=self.bytes)

    def to_uuid4(self) -> uuid.UUID:
        """Convert the :class:`ULID` to a :class:`uuid.UUID` compliant to version 4 of RFC 4122.

        This conversion is destructive in the sense that the :class:`uuid.UUID` cannot be converted
        back to the same :class:`ULID`. This is because the bits for the `variant` and `version`
        information have to be set accordingly changing the original byte sequence.

        Examples:

            >>> ulid = ULID()
            >>> uuid = ulid.to_uuid4()
            >>> uuid.version
            4
        """
        return uuid.UUID(bytes=self.bytes, version=4)

    def __repr__(self) -> str:
        return f"ULID({self!s})"

    def __str__(self) -> str:
        """Encode this object as a 26 character string sequence."""
        return base32.encode(self.bytes)

    def __int__(self) -> int:
        """Encode this object as an integer."""
        return int.from_bytes(self.bytes, byteorder="big")

    def __bytes__(self) -> bytes:
        """Encode this object as byte sequence."""
        return self.bytes

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ULID):
            return self.bytes < other.bytes
        if isinstance(other, int):
            return int(self) < other
        if isinstance(other, bytes):
            return self.bytes < other
        if isinstance(other, str):
            return str(self) < other
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ULID):
            return self.bytes == other.bytes
        if isinstance(other, int):
            return int(self) == other
        if isinstance(other, bytes):
            return self.bytes == other
        if isinstance(other, str):
            return str(self) == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.bytes)
