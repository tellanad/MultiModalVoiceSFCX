"""Intent classification and turn normalization node."""
import re
from typing import Any, Dict
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.graph.classifier")

PRODUCT_KEYWORDS = [
    "product",
    "axiomcart",
    "classic",
    "next",
    "ax-c100",
    "ax-n200",
    "available",
    "availability",
    "in stock",
    "stock",
    "price",
    "cost",
    "buy",
    "purchase",
    "catalog",
    "newer product",
]

SUPPORT_KEYWORDS = [
    "order",
    "ord",
    "delivery",
    "shipping",
    "track",
    "status",
    "cancel",
    "return",
    "help with order",
]

ESCALATION_KEYWORDS = [
    "human",
    "agent",
    "representative",
    "operator",
    "supervisor",
    "escalate",
    "person",
]


def classify_turn(state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes the latest turn and classifies intent into product, support, or escalation."""
    turns = state.get("turns", [])
    if not turns:
        return {"intents": ["unsupported"]}

    latest_text = turns[-1].get("content", "").strip()
    lower_text = latest_text.lower()
    logger.info("classifying_turn", utterance=latest_text)

    intents = []
    # Check escalation first
    if any(k in lower_text for k in ESCALATION_KEYWORDS):
        intents.append("escalate")
        return {
            "intents": intents,
            "escalation": {
                "reason": "customer_requested_human",
                "summary": f"Customer requested a human representative: '{latest_text}'",
                "priority": "High",
            },
        }

    # Check product intent
    has_product = any(k in lower_text for k in PRODUCT_KEYWORDS)
    if has_product:
        intents.append("product")

    # Check support intent
    has_support = any(k in lower_text for k in SUPPORT_KEYWORDS)
    if has_support:
        intents.append("support")

    if not intents:
        intents.append("unsupported")

    # Extract order number if present
    order_match = re.search(r"\b(ORD\d+|order\s*#?\s*([A-Za-z0-9\-]+))\b", latest_text, re.IGNORECASE)
    extracted_order = None
    if order_match:
        extracted_order = order_match.group(1).upper()
        if extracted_order.startswith("ORDER"):
            extracted_order = re.sub(r"ORDER\s*#?\s*", "", extracted_order).strip()

    # Determine product query
    product_query = None
    if has_product:
        if "next" in lower_text or "newer" in lower_text or "ax-n200" in lower_text:
            product_query = "AxiomCart Next"
        elif "classic" in lower_text or "ax-c100" in lower_text:
            product_query = "AxiomCart Classic"
        else:
            product_query = "AxiomCart"

    return {
        "intents": intents,
        "product_request": product_query or state.get("product_request"),
        "support_request": extracted_order or state.get("support_request"),
    }
