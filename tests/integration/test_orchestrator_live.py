"""Live end-to-end integration tests combining LangGraph orchestrator with real Salesforce org."""
import pytest
from axiomcart.config import settings
from axiomcart.graph.orchestrator import create_orchestrator
from axiomcart.integrations.inventory import MockInventoryAdapter
from axiomcart.integrations.salesforce import SalesforceClient


@pytest.fixture
def live_orchestrator():
    if not settings.salesforce_client_id or not settings.salesforce_client_secret.get_secret_value():
        pytest.skip("Salesforce credentials not configured in .env")
    sf_client = SalesforceClient()
    inv_adapter = MockInventoryAdapter()
    return create_orchestrator(salesforce_client=sf_client, inventory_adapter=inv_adapter)


@pytest.mark.asyncio
async def test_live_product_orchestration(live_orchestrator):
    thread_id = "live_test_thread_prod"
    config = {"configurable": {"thread_id": thread_id}}

    state = {
        "thread_id": thread_id,
        "turns": [{"role": "user", "content": "Is AxiomCart Classic in stock and what is the price?"}],
    }

    result = await live_orchestrator.ainvoke(state, config=config)
    assert "product" in result["intents"]
    assert result["product_result"]["status"] == "ok"
    assert result["product_result"]["product"]["sku"] == "AX-C100"
    assert float(result["product_result"]["product"]["price"]["amount"]) == 99.99
    assert result["product_result"]["inventory"]["availability"] == "in_stock"
    assert "99.99" in result["final_response"]["display_text"]


@pytest.mark.asyncio
async def test_live_combined_product_and_order_ord102(live_orchestrator):
    thread_id = "live_test_thread_combined"
    config = {"configurable": {"thread_id": thread_id}}

    state = {
        "thread_id": thread_id,
        "customer": {"verified": True, "customer_id": "001bm0000384s25AAA", "name": "Maya Chen"},
        "turns": [{
            "role": "user",
            "content": "I need help with order ORD102, and I also want to know whether the newer product is available.",
        }],
    }

    result = await live_orchestrator.ainvoke(state, config=config)
    assert "product" in result["intents"]
    assert "support" in result["intents"]

    # Product assertion against live Salesforce Next product
    assert result["product_result"]["status"] == "ok"
    assert result["product_result"]["product"]["sku"] == "AX-N200"
    assert float(result["product_result"]["product"]["price"]["amount"]) == 129.99

    # Order assertion against live Salesforce ORD102 record
    assert result["support_result"]["status"] == "ok"
    assert result["support_result"]["order"]["external_order_id"] == "ORD102"
    assert result["support_result"]["order"]["status"] == "Draft"

    final_resp = result["final_response"]
    assert "AxiomCart Next" in final_resp["display_text"]
    assert "ORD102" in final_resp["display_text"]
    assert "Draft" in final_resp["display_text"]
