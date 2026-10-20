"""LiveKit WebRTC voice session token and room manager."""
from typing import Optional
from livekit.api import AccessToken, VideoGrants
from pydantic import SecretStr

from axiomcart.config import settings
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.integrations.livekit")


class LiveKitService:
    """Manages LiveKit room access tokens and grants."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[SecretStr] = None,
        livekit_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.livekit_api_key or "devkey"
        secret_raw = api_secret or settings.livekit_api_secret or SecretStr("secret")
        self.api_secret = secret_raw.get_secret_value() if isinstance(secret_raw, SecretStr) else str(secret_raw)
        self.livekit_url = livekit_url or settings.livekit_url or "wss://livekit.example.com"

    def create_token(
        self,
        room_name: str,
        participant_identity: str,
        participant_name: Optional[str] = None,
    ) -> str:
        """Generates a signed JWT token allowing a browser participant to join a voice room."""
        logger.info("generating_livekit_token", room=room_name, identity=participant_identity)

        grants = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )

        token = (
            AccessToken(self.api_key, self.api_secret)
            .with_identity(participant_identity)
            .with_name(participant_name or participant_identity)
            .with_grants(grants)
        )

        return token.to_jwt()
