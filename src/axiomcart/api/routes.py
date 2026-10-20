"""API routes for healthcheck and voice session turns."""
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from langgraph.types import Command

from axiomcart.config import settings
from axiomcart.graph.orchestrator import create_orchestrator
from axiomcart.models.state import FinalSynthesizedResponse
from axiomcart.models.turn import InterruptionDetail, TurnRequest, TurnResponse
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.api.routes")
router = APIRouter()

# Global orchestrator instance for runtime API execution
_orchestrator_instance = None


def get_orchestrator():
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = create_orchestrator()
    return _orchestrator_instance


@router.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Basic service liveness probe."""
    return {
        "status": "healthy",
        "service": "axiomcart",
        "env": settings.app_env,
        "salesforce_instance": str(settings.salesforce_instance_url),
    }


@router.get("/health/ready", tags=["Health"])
async def readiness_check() -> Dict[str, Any]:
    """Readiness probe verifying configuration."""
    has_sf_creds = bool(
        settings.salesforce_client_id and settings.salesforce_client_secret.get_secret_value()
    )
    return {
        "status": "ready" if has_sf_creds else "partially_ready",
        "salesforce_configured": has_sf_creds,
        "inventory_provider": settings.inventory_provider,
    }



class TokenRequest(BaseModel):
    """Payload to request a LiveKit room token."""
    room_name: Optional[str] = None
    identity: Optional[str] = None
    name: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response for LiveKit WebRTC client connection."""
    token: str
    room_name: str
    livekit_url: str


@router.post("/api/sessions/token", response_model=TokenResponse, tags=["Session"])
async def create_session_token(req: TokenRequest) -> TokenResponse:
    """Generates a LiveKit JWT token for the browser voice client."""
    from axiomcart.integrations.livekit import LiveKitService

    room_name = req.room_name or f"room_{uuid.uuid4().hex[:8]}"
    identity = req.identity or f"user_{uuid.uuid4().hex[:6]}"
    service = LiveKitService()
    token = service.create_token(
        room_name=room_name,
        participant_identity=identity,
        participant_name=req.name,
    )

    return TokenResponse(
        token=token,
        room_name=room_name,
        livekit_url=service.livekit_url,
    )



@router.post("/api/sessions/turn", response_model=TurnResponse, tags=["Session"])
async def execute_turn(
    request: TurnRequest,
    orchestrator: Any = Depends(get_orchestrator),
) -> TurnResponse:
    """Dispatches a speech or text turn into the LangGraph orchestrator."""
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    logger.info("received_turn_request", thread_id=thread_id, transcript=request.transcript)

    if not request.is_final:
        return TurnResponse(
            thread_id=thread_id,
            status="partial_ignored",
        )

    try:
        # Check if the thread is currently paused on an interrupt
        snapshot = await orchestrator.aget_state(config)
        has_pending_interrupt = bool(snapshot.tasks and snapshot.tasks[0].interrupts)

        if has_pending_interrupt:
            # Resume using resume_value or latest transcript
            resume_arg = request.resume_value or request.transcript
            logger.info("resuming_interrupted_graph", thread_id=thread_id, resume_arg=resume_arg)
            await orchestrator.ainvoke(Command(resume=resume_arg), config=config)
        else:
            turn_payload = {
                "thread_id": thread_id,
                "livekit_session_id": request.session_id,
                "turns": [{"role": "user", "content": request.transcript}],
            }
            await orchestrator.ainvoke(turn_payload, config=config)

        # Inspect updated state snapshot
        post_snapshot = await orchestrator.aget_state(config)

        if post_snapshot.tasks and post_snapshot.tasks[0].interrupts:
            int_val = post_snapshot.tasks[0].interrupts[0].value
            return TurnResponse(
                thread_id=thread_id,
                status="interrupted",
                interruption=InterruptionDetail(
                    field=int_val.get("field", "unknown"),
                    question=int_val.get("question", "Could you provide additional information?"),
                ),
            )

        values = post_snapshot.values
        final_resp = values.get("final_response")
        parsed_resp = FinalSynthesizedResponse(**final_resp) if final_resp else None

        if values.get("escalation"):
            return TurnResponse(
                thread_id=thread_id,
                status="escalated",
                final_response=parsed_resp,
            )

        return TurnResponse(
            thread_id=thread_id,
            status="completed",
            final_response=parsed_resp,
        )

    except Exception as exc:
        logger.error("turn_execution_failed", thread_id=thread_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Turn execution failed: {str(exc)}",
        ) from exc
