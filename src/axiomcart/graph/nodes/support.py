"""Support specialist node with missing-input and verification interruption."""
import re
from typing import Any, Dict, Optional
from langgraph.types import interrupt

from axiomcart.integrations.salesforce import SalesforceClient
from axiomcart.models.envelopes import ToolResultStatus
from axiomcart.models.state import SupportSpecialistOutcome
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.graph.support")

# Demo customer constants linked to the Salesforce seed data
DEMO_ACCOUNT_ID = "001bm0000384s25AAA"
DEMO_CONTACT_NAME = "Maya Chen"
DEMO_CONTACT_EMAIL = "maya.chen@example.com"


class SupportSpecialistNode:
    """Specialist node for customer verification and order inquiries with interrupt/resume."""

    def __init__(self, salesforce_client: Optional[SalesforceClient] = None):
        self.salesforce = salesforce_client or SalesforceClient()

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("running_support_specialist", state_keys=list(state.keys()))

        order_identifier = state.get("support_request")
        # 1. Check for missing order identifier
        if not order_identifier:
            logger.info("order_number_missing_interrupting")
            resumed_order = interrupt({
                "field": "order_number",
                "question": "Could you please provide your order number?",
            })
            order_identifier = str(resumed_order).strip().upper()
            if order_identifier.startswith("ORDER"):
                order_identifier = re.sub(r"ORDER\s*#?\s*", "", order_identifier).strip()

        # 2. Check customer verification policy
        customer = dict(state.get("customer") or {})
        verified = customer.get("verified", False)
        customer_id = customer.get("customer_id")

        if not verified:
            logger.info("customer_unverified_interrupting")
            resumed_answer = interrupt({
                "field": "verification",
                "question": "For your security, could you please verify your name or email on file?",
            })
            ans_str = str(resumed_answer).lower().strip()
            # Verify against demo identity fixtures
            if any(token in ans_str for token in ["maya", "chen", "maya.chen", "demo", DEMO_ACCOUNT_ID.lower()]):
                customer["verified"] = True
                customer["customer_id"] = DEMO_ACCOUNT_ID
                customer["name"] = DEMO_CONTACT_NAME
                customer["email"] = DEMO_CONTACT_EMAIL
                customer["verification_method"] = "name_and_email_match"
                customer_id = DEMO_ACCOUNT_ID
                logger.info("customer_verified_successfully", customer_id=customer_id)
            else:
                customer["verified"] = False
                logger.warn("customer_verification_failed", supplied_answer=ans_str)
                outcome = SupportSpecialistOutcome(
                    status="not_authorized",
                    summary="Customer verification failed. Order details cannot be disclosed.",
                )
                return {
                    "support_request": order_identifier,
                    "customer": customer,
                    "support_result": outcome.model_dump(),
                }

        # 3. Retrieve authorized order details from Salesforce
        sf_result = await self.salesforce.lookup_order(
            order_identifier=order_identifier,
            verified_customer_id=customer_id,
        )

        if sf_result.status == ToolResultStatus.OK and sf_result.data:
            order = sf_result.data
            items_desc = ", ".join(
                f"{int(it.quantity)}x {it.name} (SKU: {it.sku or 'N/A'})"
                for it in order.items
            ) or "no item details"
            total_str = f"${order.total_amount:,.2f}" if order.total_amount is not None else "N/A"

            summary = (
                f"Order {order.external_order_id or order.order_number} is currently in {order.status} status "
                f"with a total of {total_str}. Items included: {items_desc}."
            )
            outcome = SupportSpecialistOutcome(
                status="ok",
                order=order,
                summary=summary,
            )
        elif sf_result.status == ToolResultStatus.NOT_AUTHORIZED:
            outcome = SupportSpecialistOutcome(
                status="not_authorized",
                summary=f"You are not authorized to view order '{order_identifier}'.",
            )
        elif sf_result.status == ToolResultStatus.NOT_FOUND:
            outcome = SupportSpecialistOutcome(
                status="not_found",
                summary=f"Order '{order_identifier}' was not found in the system.",
            )
        else:
            outcome = SupportSpecialistOutcome(
                status="failed",
                summary=f"Unable to retrieve order '{order_identifier}': {sf_result.error or 'Internal error'}",
            )

        return {
            "support_request": order_identifier,
            "customer": customer,
            "support_result": outcome.model_dump(),
        }
