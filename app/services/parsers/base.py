from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class ParsedSignal:
    """The extracted failure signal for a single log, independent of format."""

    format: str
    error_type: Optional[str] = None
    message: str = ""
    file: Optional[str] = None
    line: Optional[int] = None
    context: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "error_type": self.error_type,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "context": self.context,
            "extra": self.extra,
        }


class Parser(Protocol):
    """Common interface every format-specific parser implements."""

    def parse(self, log: str) -> ParsedSignal: ...
