"""Chat request and response schemas."""

from typing import List, Literal, Optional
from pydantic import BaseModel
from .ui import FeatureInstruction


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatMetadata(BaseModel):
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    locale: Optional[str] = "vi-VN"


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    meta: Optional[ChatMetadata] = None


class ChatResponse(BaseModel):
    reply: str
    ui_effects: List[FeatureInstruction] = []
    raw_agent_output: Optional[dict] = None
