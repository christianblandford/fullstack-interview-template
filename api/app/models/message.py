from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    document: str
    chunk: str
    score: float


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class MessageCreate(BaseModel):
    content: str


class ToolCall(BaseModel):
    name: str
    args: dict


class MessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[Source] = []
    tool_calls: list[ToolCall] = []
    usage: Usage | None = None
    created_at: datetime


class StreamEvent(BaseModel):
    """SSE event payload sent to the client during streaming."""

    event: Literal["token", "sources", "done", "error", "tool_call", "usage"]
    data: str | list[Source] | MessageResponse | Usage | None = None
