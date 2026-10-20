"""Response synthesizer node creating display and speech-ready answers."""
from typing import Any, Dict, List
from axiomcart.models.state import FinalSynthesizedResponse
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.graph.synthesizer")


def synthesize_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """Combines specialist outcomes into grounded display and speech-ready text."""
    logger.info("synthesizing_response", state_keys=list(state.keys()))

    escalation = state.get("escalation")
    if escalation:
        case_id = escalation.get("case_id")
        case_note = f" I have created case #{case_id} for you." if case_id else " I am routing this to our team."
        display_text = f"**Escalation Notice:** {escalation.get('summary')}{case_note}"
        speech_text = f"I've escalated your request to a representative.{case_note} Someone will assist you shortly."
        return {
            "final_response": FinalSynthesizedResponse(
                display_text=display_text,
                speech_text=speech_text,
                citations=["Salesforce Case Routing"],
            ).model_dump()
        }

    display_parts: List[str] = []
    speech_parts: List[str] = []
    citations: List[str] = []

    product_res = state.get("product_result")
    if product_res:
        summary = product_res.get("summary", "")
        if summary:
            display_parts.append(f"**Product Information:**\n{summary}")
            speech_parts.append(summary)
            citations.extend(["Salesforce Product2", "Inventory Management"])

    support_res = state.get("support_result")
    if support_res:
        summary = support_res.get("summary", "")
        if summary:
            display_parts.append(f"**Support & Order Status:**\n{summary}")
            speech_parts.append(summary)
            citations.append("Salesforce Orders")

    if not display_parts:
        display_text = "I wasn't able to find the information you requested. Would you like me to connect you with an agent?"
        speech_text = "I wasn't able to find that information. Would you like to speak with a representative?"
    else:
        display_text = "\n\n".join(display_parts)
        speech_text = " ".join(speech_parts)

    return {
        "final_response": FinalSynthesizedResponse(
            display_text=display_text,
            speech_text=speech_text,
            citations=list(set(citations)),
        ).model_dump()
    }
