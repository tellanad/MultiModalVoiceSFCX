"""Unit tests for FastAPI endpoints and session turn handling."""
import pytest
from httpx import ASGITransport, AsyncClient

from axiomcart.api.routes import get_orchestrator
from axiomcart.graph.orchestrator import create_orchestrator
from axiomcart.integrations.inventory import MockInventoryAdapter
from axiomcart.main import create_app
from tests.unit.test_orchestrator import MockSalesforceClient


@pytest.fixture
def test_app():
    app = create_app()
    # Inject mock orchestrator for deterministic API testing
    mock_sf = MockSalesforceClient()
    mock_inv = MockInventoryAdapter()
    mock_orch = create_orchestrator(salesforce_client=mock_sf, inventory_adapter=mock_inv)
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch
    return app


@pytest.mark.asyncio
async def test_health_endpoints(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "axiomcart"

        ready_resp = await client.get("/health/ready")
        assert ready_resp.status_code == 200
        ready_data = ready_resp.json()
        assert "salesforce_configured" in ready_data

        root_resp = await client.get("/")
        assert root_resp.status_code == 200
        assert "AxiomCart Voice AI" in root_resp.text



@pytest.mark.asyncio
async def test_create_session_token(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"room_name": "test_room", "identity": "tester_1"}
        resp = await client.post("/api/sessions/token", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_name"] == "test_room"
        assert "token" in data
        assert len(data["token"]) > 20


@pytest.mark.asyncio
async def test_api_product_turn(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "transcript": "Is AxiomCart Classic in stock?",
            "thread_id": "api_test_prod_1",
            "is_final": True,
        }
        resp = await client.post("/api/sessions/turn", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["final_response"] is not None
        assert "AxiomCart Classic" in data["final_response"]["display_text"]


@pytest.mark.asyncio
async def test_api_turn_interrupt_and_resume_flow(test_app):
    transport = ASGITransport(app=test_app)
    thread_id = "api_test_flow_1"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ask for order assistance without providing order number
        turn1 = {
            "transcript": "I need help with my order",
            "thread_id": thread_id,
            "is_final": True,
        }
        resp1 = await client.post("/api/sessions/turn", json=turn1)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "interrupted"
        assert data1["interruption"]["field"] == "order_number"

        # 2. Provide order number ORD102
        turn2 = {
            "transcript": "ORD102",
            "thread_id": thread_id,
            "is_final": True,
        }
        resp2 = await client.post("/api/sessions/turn", json=turn2)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "interrupted"
        assert data2["interruption"]["field"] == "verification"

        # 3. Provide verification
        turn3 = {
            "transcript": "My name is Maya Chen",
            "thread_id": thread_id,
            "is_final": True,
        }
        resp3 = await client.post("/api/sessions/turn", json=turn3)
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["status"] == "completed"
        assert data3["final_response"] is not None
        assert "ORD102" in data3["final_response"]["display_text"]
