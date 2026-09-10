from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    log: str = Field(..., description="Raw log text to diagnose.")
    format_hint: Optional[Literal["python", "npm", "docker"]] = Field(
        None, description="Optional hint to skip auto-detection."
    )


class ErrorSignal(BaseModel):
    format: str
    error_type: Optional[str] = None
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    context: str
    extra: dict[str, Any] = Field(default_factory=dict)


class DiagnoseResponse(BaseModel):
    detected_format: str
    error_signal: ErrorSignal
    cause: str
    explanation: str
    fix: str
    commands: list[str]
    source: Literal["pattern", "llm"] = Field(
        ..., description="'pattern' = matched a known, common issue. 'llm' = novel issue, Claude's best analysis."
    )
    pattern_id: Optional[str] = Field(
        None, description="Which pattern in the database matched, when source == 'pattern'."
    )
