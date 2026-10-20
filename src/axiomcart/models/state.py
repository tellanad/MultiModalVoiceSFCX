"""LangGraph state contracts and specialist outcome schemas."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from axiomcart.models.inventory import InventoryAvailability
from axiomcart.models.salesforce import OrderLookupResult, ProductMatch


class CustomerIdentity(BaseModel):
    """Customer identity and verification status."""
    verified: bool = False
    customer_id: Optional[str] = None  # Salesforce Account or Contact ID
    name: Optional[str] = None
    email: Optional[str] = None
    verification_method: Optional[str] = None


class ProductSpecialistOutcome(BaseModel):
    """Outcome produced by the Product specialist."""
    status: str = "ok"  # ok | not_found | failed
    product: Optional[ProductMatch] = None
    inventory: Optional[InventoryAvailability] = None
    summary: str = ""


class SupportSpecialistOutcome(BaseModel):
    """Outcome produced by the Support specialist."""
    status: str = "ok"  # ok | not_found | not_authorized | failed
    order: Optional[OrderLookupResult] = None
    summary: str = ""


class PendingInputRequest(BaseModel):
    """Structured request emitted during an interrupt."""
    field: str  # e.g., "order_number", "verification"
    question: str
    context: Dict[str, Any] = Field(default_factory=dict)


class EscalationDetail(BaseModel):
    """Details when conversation escalates to a human agent."""
    reason: str
    summary: str
    case_id: Optional[str] = None
    priority: str = "Medium"


class FinalSynthesizedResponse(BaseModel):
    """Grounded final response containing both visual and speech representations."""
    display_text: str
    speech_text: str
    citations: List[str] = Field(default_factory=list)


class GraphState(BaseModel):
    """Shared state for the LangGraph orchestrator."""
    thread_id: str
    call_id: Optional[str] = None
    livekit_session_id: Optional[str] = None
    salesforce_case_id: Optional[str] = None
    customer: CustomerIdentity = Field(default_factory=CustomerIdentity)
    turns: List[Dict[str, str]] = Field(default_factory=list)
    intents: List[str] = Field(default_factory=list)
    product_request: Optional[str] = None
    support_request: Optional[str] = None
    product_result: Optional[ProductSpecialistOutcome] = None
    support_result: Optional[SupportSpecialistOutcome] = None
    pending_input: Optional[PendingInputRequest] = None
    escalation: Optional[EscalationDetail] = None
    final_response: Optional[FinalSynthesizedResponse] = None
    errors: List[str] = Field(default_factory=list)


from typing import TypedDict


class GraphStateDict(TypedDict, total=False):
    """TypedDict representation for LangGraph graph channels."""
    thread_id: str
    call_id: Optional[str]
    livekit_session_id: Optional[str]
    salesforce_case_id: Optional[str]
    customer: Dict[str, Any]
    turns: List[Dict[str, str]]
    intents: List[str]
    product_request: Optional[str]
    support_request: Optional[str]
    product_result: Optional[Dict[str, Any]]
    support_result: Optional[Dict[str, Any]]
    pending_input: Optional[Dict[str, Any]]
    escalation: Optional[Dict[str, Any]]
    final_response: Optional[Dict[str, Any]]
    errors: List[str]

