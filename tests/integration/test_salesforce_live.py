"""Live integration tests against the configured Salesforce Developer Edition org."""
import pytest
from axiomcart.config import settings
from axiomcart.integrations.salesforce import SalesforceClient
from axiomcart.models.envelopes import ToolResultStatus


@pytest.fixture
def live_client():
    if not settings.salesforce_client_id or not settings.salesforce_client_secret.get_secret_value():
        pytest.skip("Salesforce credentials not configured in .env")
    return SalesforceClient()


@pytest.mark.asyncio
async def test_live_salesforce_authentication(live_client):
    token = await live_client.authenticate()
    assert token is not None
    assert len(token) > 20


@pytest.mark.asyncio
async def test_live_lookup_axiomcart_classic(live_client):
    result = await live_client.lookup_products("AX-C100")
    assert result.status == ToolResultStatus.OK
    assert result.data is not None
    assert len(result.data.matches) > 0
    match = result.data.matches[0]
    assert match.sku == "AX-C100"
    assert "AxiomCart" in match.name
    assert match.price is not None
    assert float(match.price.amount) == 99.99


@pytest.mark.asyncio
async def test_live_lookup_axiomcart_next(live_client):
    result = await live_client.lookup_products("AX-N200")
    assert result.status == ToolResultStatus.OK
    assert result.data is not None
    assert len(result.data.matches) > 0
    match = result.data.matches[0]
    assert match.sku == "AX-N200"
    assert match.price is not None
    assert float(match.price.amount) == 129.99


@pytest.mark.asyncio
async def test_live_lookup_order_ord102(live_client):
    result = await live_client.lookup_order("ORD102")
    assert result.status == ToolResultStatus.OK
    assert result.data is not None
    assert result.data.external_order_id == "ORD102"
    assert result.data.status == "Draft"
    assert len(result.data.items) >= 2
    # Verify items contain GC1020 or SL9020 as configured in seed data
    skus = [i.sku for i in result.data.items if i.sku]
    assert any(sku in ["GC1020", "SL9020"] for sku in skus)


@pytest.mark.asyncio
async def test_live_lookup_order_unauthorized(live_client):
    # Pass an arbitrary customer/account ID that doesn't own ORD102
    result = await live_client.lookup_order("ORD102", verified_customer_id="001FAKEACCOUNTID")
    assert result.status == ToolResultStatus.NOT_AUTHORIZED
    assert result.data is None
