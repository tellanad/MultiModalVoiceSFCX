"""Inventory / OMS adapter interface and deterministic mock implementation."""
from typing import Dict, Optional
from axiomcart.models.envelopes import ToolResult, ToolResultStatus
from axiomcart.models.inventory import AvailabilityStatus, InventoryAvailability
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.integrations.inventory")


class MockInventoryAdapter:
    """Deterministic in-memory inventory adapter for development and testing."""

    def __init__(self, seed_data: Optional[Dict[str, InventoryAvailability]] = None):
        self._stock: Dict[str, InventoryAvailability] = seed_data or {
            "AX-C100": InventoryAvailability(
                sku="AX-C100",
                availability=AvailabilityStatus.IN_STOCK,
                available_quantity=42,
                fulfillment_note="In stock at primary fulfillment center; ships within 24 hours.",
            ),
            "AX-N200": InventoryAvailability(
                sku="AX-N200",
                availability=AvailabilityStatus.IN_STOCK,
                available_quantity=15,
                fulfillment_note="New release in stock; ships within 1-2 business days.",
            ),
            "GC1020": InventoryAvailability(
                sku="GC1020",
                availability=AvailabilityStatus.LOW_STOCK,
                available_quantity=2,
                fulfillment_note="Low stock alert: only 2 units remain; restock arrives next week.",
            ),
            "SL9020": InventoryAvailability(
                sku="SL9020",
                availability=AvailabilityStatus.IN_STOCK,
                available_quantity=999,
                fulfillment_note="Digital service entitlement; immediate activation.",
            ),
        }

    async def check_availability(
        self,
        sku: str,
        location: Optional[str] = None,
        requested_quantity: int = 1,
    ) -> ToolResult[InventoryAvailability]:
        """Check stock availability for the given SKU."""
        clean_sku = sku.strip().upper()
        logger.info("checking_inventory", sku=clean_sku, requested_qty=requested_quantity)

        if not clean_sku:
            return ToolResult.failed(
                "SKU must not be empty",
                source="inventory",
                status=ToolResultStatus.INVALID,
            )

        if clean_sku in self._stock:
            item = self._stock[clean_sku]
            return ToolResult.ok(item, source="inventory")

        # Unknown or unlisted SKU defaults to out of stock
        out_of_stock_item = InventoryAvailability(
            sku=clean_sku,
            availability=AvailabilityStatus.OUT_OF_STOCK,
            available_quantity=0,
            fulfillment_note="Item is currently out of stock or discontinued.",
        )
        return ToolResult.ok(out_of_stock_item, source="inventory")
