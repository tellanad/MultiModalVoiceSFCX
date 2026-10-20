"""Salesforce Service Cloud REST API adapter."""
import re
from typing import Any, Dict, List, Optional
import httpx
from pydantic import HttpUrl, SecretStr

from axiomcart.config import settings
from axiomcart.models.envelopes import ToolResult, ToolResultStatus
from axiomcart.models.salesforce import (
    CaseUpsertInput,
    CaseUpsertResult,
    OrderItemDetail,
    OrderLookupResult,
    Price,
    ProductLookupResult,
    ProductMatch,
)
from axiomcart.observability.logging import get_logger

logger = get_logger("axiomcart.integrations.salesforce")


def sanitize_soql_string(value: str) -> str:
    """Escapes single quotes and control characters to prevent SOQL injection."""
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", value)
    return sanitized.replace("'", "\\'")


class SalesforceClient:
    """Async client for Salesforce OAuth2 and REST APIs."""

    def __init__(
        self,
        instance_url: Optional[HttpUrl] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[SecretStr] = None,
        api_version: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.instance_url = str(instance_url or settings.salesforce_instance_url).rstrip("/")
        self.client_id = client_id or settings.salesforce_client_id
        self.client_secret = client_secret or settings.salesforce_client_secret
        self.api_version = api_version or settings.salesforce_api_version
        self._http_client = http_client
        self._access_token: Optional[str] = None
        self._token_instance_url: Optional[str] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

    async def authenticate(self, force_refresh: bool = False) -> str:
        """Acquires a Salesforce access token using OAuth 2.0 Client Credentials flow."""
        if self._access_token and not force_refresh:
            return self._access_token

        client = self._get_client()
        token_endpoint = f"{self.instance_url}/services/oauth2/token"
        secret_val = self.client_secret.get_secret_value() if isinstance(self.client_secret, SecretStr) else str(self.client_secret)

        logger.info("authenticating_salesforce", instance_url=self.instance_url)

        try:
            response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": secret_val,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]
            self._token_instance_url = data.get("instance_url", self.instance_url).rstrip("/")
            logger.info("salesforce_authenticated", token_scope=data.get("scope"))
            return self._access_token
        except httpx.HTTPStatusError as exc:
            logger.error("salesforce_auth_failed", status_code=exc.response.status_code, error=exc.response.text)
            raise RuntimeError(f"Salesforce authentication failed: {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("salesforce_auth_exception", error=str(exc))
            raise

    async def _execute_soql(self, soql: str, retried: bool = False) -> Dict[str, Any]:
        """Executes a SOQL query using the REST API."""
        token = await self.authenticate()
        base_url = self._token_instance_url or self.instance_url
        endpoint = f"{base_url}/services/data/{self.api_version}/query"
        client = self._get_client()

        response = await client.get(
            endpoint,
            params={"q": soql},
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code == 401 and not retried:
            logger.warn("salesforce_token_expired_retrying")
            self._access_token = None
            return await self._execute_soql(soql, retried=True)

        response.raise_for_status()
        return response.json()

    async def lookup_products(
        self, query: str, pricebook_id: Optional[str] = None
    ) -> ToolResult[ProductLookupResult]:
        """Queries active products and their standard or specified pricebook entries."""
        sanitized = sanitize_soql_string(query.strip())
        if not sanitized:
            return ToolResult.failed("Product query cannot be empty", source="salesforce", status=ToolResultStatus.INVALID)

        soql = (
            f"SELECT Id, Name, ProductCode, Description FROM Product2 "
            f"WHERE IsActive = true AND (ProductCode = '{sanitized}' OR Name LIKE '%{sanitized}%') "
            f"LIMIT 5"
        )

        try:
            result = await self._execute_soql(soql)
            records = result.get("records", [])
            if not records:
                return ToolResult.not_found(f"No products found matching '{query}'", source="salesforce")

            product_ids = [r["Id"] for r in records]
            id_list_str = "','".join(product_ids)

            if pricebook_id:
                pb_soql = (
                    f"SELECT Id, Product2Id, UnitPrice FROM PricebookEntry "
                    f"WHERE IsActive = true AND Product2Id IN ('{id_list_str}') "
                    f"AND Pricebook2Id = '{sanitize_soql_string(pricebook_id)}'"
                )
            else:
                pb_soql = (
                    f"SELECT Id, Product2Id, UnitPrice, Pricebook2.IsStandard FROM PricebookEntry "
                    f"WHERE IsActive = true AND Product2Id IN ('{id_list_str}') "
                    f"AND Pricebook2.IsStandard = true"
                )

            pb_result = await self._execute_soql(pb_soql)
            price_map = {
                entry["Product2Id"]: str(entry["UnitPrice"])
                for entry in pb_result.get("records", [])
            }

            matches: List[ProductMatch] = []
            for r in records:
                p_id = r["Id"]
                sku = r.get("ProductCode") or ""
                name = r.get("Name") or ""
                price = Price(amount=price_map[p_id]) if p_id in price_map else None
                matches.append(
                    ProductMatch(
                        product_id=p_id,
                        sku=sku,
                        name=name,
                        description=r.get("Description"),
                        price=price,
                        match_reason="exact_sku" if sku.lower() == query.strip().lower() else "name_match",
                    )
                )

            return ToolResult.ok(ProductLookupResult(matches=matches), source="salesforce")

        except Exception as exc:
            logger.error("salesforce_lookup_products_failed", query=query, error=str(exc))
            return ToolResult.failed(str(exc), source="salesforce")

    async def lookup_order(
        self,
        order_identifier: str,
        verified_customer_id: Optional[str] = None,
    ) -> ToolResult[OrderLookupResult]:
        """Queries Order and OrderItems by external or system order identifier."""
        sanitized = sanitize_soql_string(order_identifier.strip())
        if not sanitized:
            return ToolResult.failed("Order identifier cannot be empty", source="salesforce", status=ToolResultStatus.INVALID)

        soql = (
            f"SELECT Id, OrderNumber, External_Order_ID__c, Status, TotalAmount, AccountId, Account.Name "
            f"FROM Order "
            f"WHERE External_Order_ID__c = '{sanitized}' OR OrderNumber = '{sanitized}' "
            f"LIMIT 1"
        )

        try:
            result = await self._execute_soql(soql)
            records = result.get("records", [])
            if not records:
                return ToolResult.not_found(f"Order '{order_identifier}' not found", source="salesforce")

            order_data = records[0]
            account_id = order_data.get("AccountId")

            # Check customer authorization if verified customer ID provided
            if verified_customer_id and account_id and account_id != verified_customer_id:
                logger.warn("unauthorized_order_access", verified_id=verified_customer_id, order_account=account_id)
                return ToolResult.not_authorized(
                    "You are not authorized to view this order.", source="salesforce"
                )

            order_id = order_data["Id"]
            items_soql = (
                f"SELECT Id, OrderId, PricebookEntry.Product2.Name, PricebookEntry.Product2.ProductCode, "
                f"Quantity, UnitPrice, TotalPrice "
                f"FROM OrderItem WHERE OrderId = '{order_id}'"
            )
            items_result = await self._execute_soql(items_soql)

            items: List[OrderItemDetail] = []
            for item in items_result.get("records", []):
                p2 = item.get("PricebookEntry", {}).get("Product2", {}) or {}
                items.append(
                    OrderItemDetail(
                        item_id=item["Id"],
                        sku=p2.get("ProductCode"),
                        name=p2.get("Name", "Unknown Product"),
                        quantity=float(item.get("Quantity", 1)),
                        unit_price=float(item.get("UnitPrice", 0.0)) if item.get("UnitPrice") is not None else None,
                        total_price=float(item.get("TotalPrice", 0.0)) if item.get("TotalPrice") is not None else None,
                    )
                )

            account = order_data.get("Account") or {}
            res = OrderLookupResult(
                order_id=order_id,
                order_number=order_data.get("OrderNumber", ""),
                external_order_id=order_data.get("External_Order_ID__c"),
                status=order_data.get("Status", "Unknown"),
                account_id=account_id,
                account_name=account.get("Name"),
                total_amount=float(order_data.get("TotalAmount", 0.0)) if order_data.get("TotalAmount") is not None else None,
                items=items,
            )
            return ToolResult.ok(res, source="salesforce")

        except Exception as exc:
            logger.error("salesforce_lookup_order_failed", order_identifier=order_identifier, error=str(exc))
            return ToolResult.failed(str(exc), source="salesforce")

    async def upsert_case(self, case_input: CaseUpsertInput) -> ToolResult[CaseUpsertResult]:
        """Creates or updates a Salesforce Case idempotently."""
        token = await self.authenticate()
        base_url = self._token_instance_url or self.instance_url
        client = self._get_client()

        body: Dict[str, Any] = {
            "Subject": case_input.subject,
            "Description": f"{case_input.summary}\n\n[Idempotency-Key: {case_input.idempotency_key}]",
            "Priority": case_input.priority,
            "Origin": "Phone",
        }
        if case_input.account_id:
            body["AccountId"] = case_input.account_id
        if case_input.contact_id:
            body["ContactId"] = case_input.contact_id

        try:
            if case_input.existing_case_id:
                endpoint = f"{base_url}/services/data/{self.api_version}/sobjects/Case/{case_input.existing_case_id}"
                resp = await client.patch(
                    endpoint,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                return ToolResult.ok(
                    CaseUpsertResult(case_id=case_input.existing_case_id, operation="updated"),
                    source="salesforce",
                )
            else:
                endpoint = f"{base_url}/services/data/{self.api_version}/sobjects/Case"
                resp = await client.post(
                    endpoint,
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return ToolResult.ok(
                    CaseUpsertResult(case_id=data["id"], operation="created"),
                    source="salesforce",
                )
        except Exception as exc:
            logger.error("salesforce_upsert_case_failed", idempotency_key=case_input.idempotency_key, error=str(exc))
            return ToolResult.failed(str(exc), source="salesforce")
