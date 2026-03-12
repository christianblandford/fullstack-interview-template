from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Source(BaseModel):
    document: str
    chunk: str
    score: float


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[Source] = []
    created_at: datetime


class StreamEvent(BaseModel):
    """SSE event payload sent to the client during streaming."""

    event: Literal["token", "sources", "done", "error"]
    data: str | list[Source] | MessageResponse | None = None
