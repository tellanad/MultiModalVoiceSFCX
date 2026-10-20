"""LangGraph orchestrator coordinating specialist fan-out, interrupts, and synthesis."""
from typing import Any, Dict, List, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from axiomcart.graph.nodes.classifier import classify_turn
from axiomcart.graph.nodes.escalation import EscalationNode
from axiomcart.graph.nodes.product import ProductSpecialistNode
from axiomcart.graph.nodes.support import SupportSpecialistNode
from axiomcart.graph.nodes.synthesizer import synthesize_response
from axiomcart.integrations.inventory import MockInventoryAdapter
from axiomcart.integrations.salesforce import SalesforceClient
from axiomcart.models.state import GraphStateDict
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.graph.orchestrator")


def route_specialists(state: Dict[str, Any]) -> List[str]:
    """Conditional router determining required specialists or escalation path."""
    intents = state.get("intents", [])
    logger.info("routing_turn", intents=intents)

    if "escalate" in intents:
        return ["escalate"]

    targets = []
    if "product" in intents:
        targets.append("product_specialist")
    if "support" in intents:
        targets.append("support_specialist")

    if not targets:
        return ["synthesize"]

    return targets


def create_orchestrator(
    salesforce_client: Optional[SalesforceClient] = None,
    inventory_adapter: Optional[MockInventoryAdapter] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
):
    """Builds and compiles the LangGraph customer service orchestrator."""
    sf_client = salesforce_client or SalesforceClient()
    inv_adapter = inventory_adapter or MockInventoryAdapter()
    saver = checkpointer if checkpointer is not None else MemorySaver()

    builder = StateGraph(GraphStateDict)

    # Add Nodes
    builder.add_node("classify", classify_turn)
    builder.add_node("product_specialist", ProductSpecialistNode(sf_client, inv_adapter))
    builder.add_node("support_specialist", SupportSpecialistNode(sf_client))
    builder.add_node("escalate", EscalationNode(sf_client))
    builder.add_node("synthesize", synthesize_response)

    # Add Graph Edges
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_specialists,
        {
            "product_specialist": "product_specialist",
            "support_specialist": "support_specialist",
            "escalate": "escalate",
            "synthesize": "synthesize",
        },
    )

    builder.add_edge("product_specialist", "synthesize")
    builder.add_edge("support_specialist", "synthesize")
    builder.add_edge("escalate", "synthesize")
    builder.add_edge("synthesize", END)

    compiled = builder.compile(checkpointer=saver)
    logger.info("orchestrator_compiled_successfully")
    return compiled
