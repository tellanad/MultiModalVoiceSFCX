"""Product specialist node combining Salesforce catalog and Inventory availability."""
from typing import Any, Dict, Optional
from axiomcart.integrations.inventory import MockInventoryAdapter
from axiomcart.integrations.salesforce import SalesforceClient
from axiomcart.models.envelopes import ToolResultStatus
from axiomcart.models.state import ProductSpecialistOutcome
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.graph.product")


class ProductSpecialistNode:
    """Specialist node for resolving product inquiries."""

    def __init__(
        self,
        salesforce_client: Optional[SalesforceClient] = None,
        inventory_adapter: Optional[MockInventoryAdapter] = None,
    ):
        self.salesforce = salesforce_client or SalesforceClient()
        self.inventory = inventory_adapter or MockInventoryAdapter()

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        product_query = state.get("product_request") or "AxiomCart"
        logger.info("running_product_specialist", query=product_query)

        sf_result = await self.salesforce.lookup_products(product_query)

        if sf_result.status != ToolResultStatus.OK or not sf_result.data or not sf_result.data.matches:
            outcome = ProductSpecialistOutcome(
                status="not_found",
                summary=f"No matching products found in the catalog for '{product_query}'.",
            )
            return {"product_result": outcome.model_dump()}

        matched_product = sf_result.data.matches[0]
        sku = matched_product.sku

        inv_result = await self.inventory.check_availability(sku)
        inv_data = inv_result.data if inv_result.status == ToolResultStatus.OK else None

        price_str = f"${matched_product.price.amount}" if matched_product.price else "price unlisted"
        avail_str = inv_data.availability.value.replace("_", " ") if inv_data else "status unknown"
        fulfillment = f" ({inv_data.fulfillment_note})" if (inv_data and inv_data.fulfillment_note) else ""

        summary = (
            f"{matched_product.name} (SKU: {sku}) is priced at {price_str} and is {avail_str}{fulfillment}."
        )

        outcome = ProductSpecialistOutcome(
            status="ok",
            product=matched_product,
            inventory=inv_data,
            summary=summary,
        )
        return {"product_result": outcome.model_dump()}
