"""Inventory and availability domain models."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class AvailabilityStatus(str, Enum):
    """Inventory availability levels."""
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class InventoryCheckInput(BaseModel):
    """Payload to check stock availability for a SKU."""
    sku: str
    location: Optional[str] = None
    requested_quantity: int = 1


class InventoryAvailability(BaseModel):
    """Stock availability returned by inventory adapter."""
    sku: str
    availability: AvailabilityStatus
    available_quantity: Optional[int] = None
    fulfillment_note: Optional[str] = None
