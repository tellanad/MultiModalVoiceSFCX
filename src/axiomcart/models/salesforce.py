"""Domain models for Salesforce catalog, orders, and support cases."""
from typing import List, Optional
from pydantic import BaseModel, Field


class Price(BaseModel):
    """Monetary amount and currency code."""
    amount: str
    currency: str = "USD"


class ProductMatch(BaseModel):
    """Product matched from Salesforce Product2 and PricebookEntry."""
    product_id: str
    sku: str
    name: str
    description: Optional[str] = None
    price: Optional[Price] = None
    match_reason: str = "exact_sku"


class ProductLookupResult(BaseModel):
    """Collection of product matches."""
    matches: List[ProductMatch] = Field(default_factory=list)


class OrderItemDetail(BaseModel):
    """Item detail within an authorized Order."""
    item_id: str
    sku: Optional[str] = None
    name: str
    quantity: float
    unit_price: Optional[float] = None
    total_price: Optional[float] = None


class OrderLookupResult(BaseModel):
    """Normalized order result returned from Salesforce."""
    order_id: str
    order_number: str
    external_order_id: Optional[str] = None
    status: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    total_amount: Optional[float] = None
    items: List[OrderItemDetail] = Field(default_factory=list)


class CaseUpsertInput(BaseModel):
    """Input payload for idempotent Case creation or update."""
    idempotency_key: str
    subject: str
    summary: str
    reason: Optional[str] = "AI_Voice_Escalation"
    priority: str = "Medium"
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    order_id: Optional[str] = None
    existing_case_id: Optional[str] = None


class CaseUpsertResult(BaseModel):
    """Result of creating or updating a Salesforce Case."""
    case_id: str
    case_number: Optional[str] = None
    operation: str = "created"  # created | updated | unchanged
