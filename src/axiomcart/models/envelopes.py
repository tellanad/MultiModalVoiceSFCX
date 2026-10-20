"""Generic tool result envelope and common enumerations."""
from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ToolResultStatus(str, Enum):
    """Execution status returned by tool and adapter operations."""
    OK = "ok"
    NOT_FOUND = "not_found"
    NOT_AUTHORIZED = "not_authorized"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    FAILED = "failed"


class ToolResult(BaseModel, Generic[T]):
    """Standard envelope for all tool and adapter responses."""
    status: ToolResultStatus
    data: Optional[T] = None
    source: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: T, source: str) -> "ToolResult[T]":
        return cls(status=ToolResultStatus.OK, data=data, source=source)

    @classmethod
    def not_found(cls, message: str, source: str) -> "ToolResult[T]":
        return cls(status=ToolResultStatus.NOT_FOUND, source=source, error=message)

    @classmethod
    def not_authorized(cls, message: str, source: str) -> "ToolResult[T]":
        return cls(status=ToolResultStatus.NOT_AUTHORIZED, source=source, error=message)

    @classmethod
    def failed(cls, message: str, source: str, status: ToolResultStatus = ToolResultStatus.FAILED) -> "ToolResult[T]":
        return cls(status=status, source=source, error=message)
