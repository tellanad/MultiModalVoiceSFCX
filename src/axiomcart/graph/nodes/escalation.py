"""Escalation node creating or updating a Salesforce Case."""
from typing import Any, Dict, Optional
from axiomcart.integrations.salesforce import SalesforceClient
from axiomcart.models.envelopes import ToolResultStatus
from axiomcart.models.salesforce import CaseUpsertInput
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.graph.escalation")


class EscalationNode:
    """Escalation node handling human handoff and Salesforce Case upsert."""

    def __init__(self, salesforce_client: Optional[SalesforceClient] = None):
        self.salesforce = salesforce_client or SalesforceClient()

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("handling_escalation", thread_id=state.get("thread_id"))
        escalation = state.get("escalation") or {
            "reason": "unhandled_intent_or_failure",
            "summary": "AI assistant was unable to resolve customer request safely.",
            "priority": "Medium",
        }

        thread_id = state.get("thread_id", "unknown_thread")
        customer = state.get("customer") or {}
        customer_id = customer.get("customer_id")

        case_input = CaseUpsertInput(
            idempotency_key=f"escalate_{thread_id}",
            subject=f"Voice Assistant Escalation ({escalation.get('reason', 'general')})",
            summary=escalation.get("summary", "Customer requested escalation"),
            priority=escalation.get("priority", "Medium"),
            account_id=customer_id if (customer_id and customer_id.startswith("001")) else None,
            contact_id=customer_id if (customer_id and customer_id.startswith("003")) else None,
        )

        sf_res = await self.salesforce.upsert_case(case_input)
        case_id = sf_res.data.case_id if sf_res.status == ToolResultStatus.OK and sf_res.data else None

        updated_escalation = dict(escalation)
        updated_escalation["case_id"] = case_id

        return {
            "escalation": updated_escalation,
            "salesforce_case_id": case_id,
        }
