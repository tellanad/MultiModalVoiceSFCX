"""Comprehensive unit tests for LangGraph orchestrator workflows."""
import pytest
from langgraph.types import Command
from pydantic import HttpUrl, SecretStr

from axiomcart.graph.orchestrator import create_orchestrator
from axiomcart.integrations.inventory import MockInventoryAdapter
from axiomcart.integrations.salesforce import SalesforceClient
from axiomcart.models.envelopes import ToolResult
from axiomcart.models.salesforce import (
    CaseUpsertResult,
    OrderItemDetail,
    OrderLookupResult,
    Price,
    ProductLookupResult,
    ProductMatch,
)


class MockSalesforceClient(SalesforceClient):
    """Deterministic mock Salesforce client for orchestrator unit testing."""

    def __init__(self):
        super().__init__(
            instance_url=HttpUrl("https://mock.salesforce.com"),
            client_id="mock_id",
            client_secret=SecretStr("mock_secret"),
        )

    async def lookup_products(self, query: str, pricebook_id=None):
        if "next" in query.lower() or "n200" in query.lower():
            p = ProductMatch(
                product_id="01t_next",
                sku="AX-N200",
                name="AxiomCart Next",
                description="Next-gen shopping assistant",
                price=Price(amount="129.99"),
                match_reason="exact_sku",
            )
            return ToolResult.ok(ProductLookupResult(matches=[p]), source="salesforce")
        else:
            p = ProductMatch(
                product_id="01t_classic",
                sku="AX-C100",
                name="AxiomCart Classic",
                description="Original shopping assistant",
                price=Price(amount="99.99"),
                match_reason="exact_sku",
            )
            return ToolResult.ok(ProductLookupResult(matches=[p]), source="salesforce")

    async def lookup_order(self, order_identifier: str, verified_customer_id=None):
        if verified_customer_id != "001bm0000384s25AAA":
            return ToolResult.not_authorized("Unauthorized customer", source="salesforce")

        if order_identifier.upper() == "ORD102":
            order = OrderLookupResult(
                order_id="801_ord102",
                order_number="00000100",
                external_order_id="ORD102",
                status="Draft",
                account_id="001bm0000384s25AAA",
                account_name="AxiomCart Demo Customer",
                total_amount=15000.0,
                items=[
                    OrderItemDetail(
                        item_id="802_item1",
                        sku="GC1020",
                        name="GenWatt Diesel 10kW",
                        quantity=1.0,
                        unit_price=5000.0,
                        total_price=5000.0,
                    ),
                    OrderItemDetail(
                        item_id="802_item2",
                        sku="SL9020",
                        name="SLA: Bronze",
                        quantity=1.0,
                        unit_price=10000.0,
                        total_price=10000.0,
                    ),
                ],
            )
            return ToolResult.ok(order, source="salesforce")

        return ToolResult.not_found(f"Order {order_identifier} not found", source="salesforce")

    async def upsert_case(self, case_input):
        return ToolResult.ok(
            CaseUpsertResult(case_id="500_MOCK_CASE_1026", operation="created"),
            source="salesforce",
        )


@pytest.fixture
def orchestrator():
    sf_mock = MockSalesforceClient()
    inv_mock = MockInventoryAdapter()
    return create_orchestrator(salesforce_client=sf_mock, inventory_adapter=inv_mock)


@pytest.mark.asyncio
async def test_product_only_inquiry(orchestrator):
    thread_id = "test_thread_prod"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "thread_id": thread_id,
        "turns": [{"role": "user", "content": "How much does AxiomCart Classic cost and is it available?"}],
    }

    result = await orchestrator.ainvoke(initial_state, config=config)
    assert "product" in result["intents"]
    assert "support" not in result["intents"]
    assert result["product_result"]["status"] == "ok"
    assert result["product_result"]["product"]["sku"] == "AX-C100"
    assert result["final_response"] is not None
    assert "AxiomCart Classic" in result["final_response"]["display_text"]
    assert "99.99" in result["final_response"]["display_text"]


@pytest.mark.asyncio
async def test_support_only_verified(orchestrator):
    thread_id = "test_thread_supp"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "thread_id": thread_id,
        "customer": {"verified": True, "customer_id": "001bm0000384s25AAA", "name": "Maya Chen"},
        "turns": [{"role": "user", "content": "Can you check status on order ORD102?"}],
    }

    result = await orchestrator.ainvoke(initial_state, config=config)
    assert "support" in result["intents"]
    assert result["support_result"]["status"] == "ok"
    assert result["support_result"]["order"]["external_order_id"] == "ORD102"
    assert "GenWatt Diesel" in result["final_response"]["display_text"]


@pytest.mark.asyncio
async def test_combined_product_and_support(orchestrator):
    thread_id = "test_thread_combined"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "thread_id": thread_id,
        "customer": {"verified": True, "customer_id": "001bm0000384s25AAA"},
        "turns": [{
            "role": "user",
            "content": "I need help with order ORD102, and I also want to know whether the newer product is available.",
        }],
    }

    result = await orchestrator.ainvoke(initial_state, config=config)
    assert "product" in result["intents"]
    assert "support" in result["intents"]
    assert result["product_result"]["status"] == "ok"
    assert result["support_result"]["status"] == "ok"

    # Both product and order details must be present in synthesized output
    final = result["final_response"]
    assert "AxiomCart Next" in final["display_text"]
    assert "ORD102" in final["display_text"]
    assert len(final["citations"]) >= 2


@pytest.mark.asyncio
async def test_interrupt_and_resume_missing_order_and_verification(orchestrator):
    thread_id = "test_thread_interrupt"
    config = {"configurable": {"thread_id": thread_id}}

    # Step 1: User asks for support without providing order number or verification
    step1_state = {
        "thread_id": thread_id,
        "customer": {"verified": False},
        "turns": [{"role": "user", "content": "I need help with my recent order"}],
    }

    res1 = await orchestrator.ainvoke(step1_state, config=config)
    # Graph halts at interrupt for order_number
    state_snap = await orchestrator.aget_state(config)
    assert len(state_snap.tasks) > 0
    interrupts = state_snap.tasks[0].interrupts
    assert len(interrupts) > 0
    assert interrupts[0].value["field"] == "order_number"

    # Step 2: Resume with order number ORD102
    res2 = await orchestrator.ainvoke(Command(resume="ORD102"), config=config)
    # Graph now interrupts for verification
    state_snap2 = await orchestrator.aget_state(config)
    assert len(state_snap2.tasks) > 0
    interrupts2 = state_snap2.tasks[0].interrupts
    assert len(interrupts2) > 0
    assert interrupts2[0].value["field"] == "verification"

    # Step 3: Resume with verified customer identity (Maya Chen)
    res3 = await orchestrator.ainvoke(Command(resume="Maya Chen"), config=config)
    # Graph finishes completely
    state_snap3 = await orchestrator.aget_state(config)
    assert len(state_snap3.tasks) == 0  # No tasks waiting
    assert res3["customer"]["verified"] is True
    assert res3["support_result"]["status"] == "ok"
    assert "ORD102" in res3["final_response"]["display_text"]


@pytest.mark.asyncio
async def test_escalation_workflow(orchestrator):
    thread_id = "test_thread_escalate"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "thread_id": thread_id,
        "turns": [{"role": "user", "content": "I want to speak with a human agent please"}],
    }

    result = await orchestrator.ainvoke(initial_state, config=config)
    assert "escalate" in result["intents"]
    assert result["salesforce_case_id"] == "500_MOCK_CASE_1026"
    assert "Escalation Notice" in result["final_response"]["display_text"]
    assert "500_MOCK_CASE_1026" in result["final_response"]["display_text"]
