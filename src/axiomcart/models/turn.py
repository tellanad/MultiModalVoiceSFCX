"""API models for session turn execution and responses."""
from typing import Optional
from pydantic import BaseModel, Field
from axiomcart.models.state import FinalSynthesizedResponse


class TurnRequest(BaseModel):
    """Payload for submitting a conversation turn from voice or chat."""
    transcript: str
    thread_id: Optional[str] = None
    session_id: Optional[str] = None
    participant_id: Optional[str] = None
    is_final: bool = True
    resume_value: Optional[str] = None


class InterruptionDetail(BaseModel):
    """Payload returned when the orchestrator requires customer input."""
    field: str
    question: str


class TurnResponse(BaseModel):
    """Response returned from a conversation turn."""
    thread_id: str
    status: str  # completed | interrupted | escalated | failed
    interruption: Optional[InterruptionDetail] = None
    final_response: Optional[FinalSynthesizedResponse] = None
    error: Optional[str] = None
