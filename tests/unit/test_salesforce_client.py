"""Unit tests for SalesforceClient using mocked HTTP responses via respx."""
import pytest
import respx
import httpx
from pydantic import HttpUrl, SecretStr

from axiomcart.integrations.salesforce import SalesforceClient, sanitize_soql_string
from axiomcart.models.envelopes import ToolResultStatus
from axiomcart.models.salesforce import CaseUpsertInput


@pytest.fixture
def sf_client():
    return SalesforceClient(
        instance_url=HttpUrl("https://test.salesforce.com"),
        client_id="test_client_id",
        client_secret=SecretStr("test_client_secret"),
        api_version="v68.0",
    )


def test_sanitize_soql_string():
    assert sanitize_soql_string("ORD102") == "ORD102"
    assert sanitize_soql_string("ORD' OR '1'='1") == "ORD\\' OR \\'1\\'=\\'1"
    assert sanitize_soql_string("test\x00query") == "testquery"


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_success(sf_client):
    respx.post("https://test.salesforce.com/services/oauth2/token").respond(
        status_code=200,
        json={
            "access_token": "test_access_token_123",
            "instance_url": "https://test.salesforce.com",
            "token_type": "Bearer",
            "scope": "api",
        },
    )

    token = await sf_client.authenticate()
    assert token == "test_access_token_123"

    # Subsequent call uses cache
    token2 = await sf_client.authenticate()
    assert token2 == "test_access_token_123"


@pytest.mark.asyncio
@respx.mock
async def test_lookup_products_success(sf_client):
    respx.post("https://test.salesforce.com/services/oauth2/token").respond(
        status_code=200,
        json={"access_token": "token", "instance_url": "https://test.salesforce.com"},
    )
    route = respx.get("https://test.salesforce.com/services/data/v68.0/query")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "records": [
                    {
                        "Id": "01t1",
                        "Name": "AxiomCart Classic",
                        "ProductCode": "AX-C100",
                        "Description": "Classic shopping assistant",
                    }
                ]
            },
        ),
        httpx.Response(
            200,
            json={
                "records": [
                    {
                        "Id": "01u1",
                        "Product2Id": "01t1",
                        "UnitPrice": 99.99,
                    }
                ]
            },
        ),
    ]

    result = await sf_client.lookup_products("AX-C100")
    assert result.status == ToolResultStatus.OK
    assert result.data is not None
    assert len(result.data.matches) == 1
    match = result.data.matches[0]
    assert match.sku == "AX-C100"
    assert match.name == "AxiomCart Classic"
    assert match.price is not None
    assert match.price.amount == "99.99"


@pytest.mark.asyncio
@respx.mock
async def test_lookup_order_unauthorized(sf_client):
    respx.post("https://test.salesforce.com/services/oauth2/token").respond(
        status_code=200,
        json={"access_token": "token", "instance_url": "https://test.salesforce.com"},
    )
    respx.get("https://test.salesforce.com/services/data/v68.0/query").respond(
        status_code=200,
        json={
            "records": [
                {
                    "Id": "8011",
                    "OrderNumber": "00000100",
                    "External_Order_ID__c": "ORD102",
                    "Status": "Draft",
                    "AccountId": "001_OTHER_ACCOUNT",
                }
            ]
        },
    )

    result = await sf_client.lookup_order("ORD102", verified_customer_id="001_VERIFIED_USER")
    assert result.status == ToolResultStatus.NOT_AUTHORIZED
    assert result.data is None


@pytest.mark.asyncio
@respx.mock
async def test_upsert_case_create(sf_client):
    respx.post("https://test.salesforce.com/services/oauth2/token").respond(
        status_code=200,
        json={"access_token": "token", "instance_url": "https://test.salesforce.com"},
    )
    respx.post("https://test.salesforce.com/services/data/v68.0/sobjects/Case").respond(
        status_code=201,
        json={"id": "500_NEW_CASE", "success": True},
    )

    case_input = CaseUpsertInput(
        idempotency_key="idemp_123",
        subject="Order issue ORD102",
        summary="Customer asked for order status",
    )
    result = await sf_client.upsert_case(case_input)
    assert result.status == ToolResultStatus.OK
    assert result.data.case_id == "500_NEW_CASE"
    assert result.data.operation == "created"
