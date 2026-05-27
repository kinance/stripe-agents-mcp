"""
stripe-agents-mcp: MCP server exposing Stripe APIs as structured tools.

25 tools covering: account, customers, products, prices, payment links,
payment intents, invoices, subscriptions, refunds, coupons, disputes,
and search/fetch utilities.

Set STRIPE_SECRET_KEY (prefer a restricted key rk_*) before running.
"""

import asyncio
import json
import os
import urllib.parse
from typing import Any

import stripe
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

app = Server("stripe-agents-mcp")

_FETCHABLE = {
    "customer": stripe.Customer,
    "product": stripe.Product,
    "price": stripe.Price,
    "invoice": stripe.Invoice,
    "subscription": stripe.Subscription,
    "payment_intent": stripe.PaymentIntent,
    "coupon": stripe.Coupon,
    "dispute": stripe.Dispute,
    "refund": stripe.Refund,
    "payment_link": stripe.PaymentLink,
}
_SEARCH_RESOURCE_MAP = {
    "customers": stripe.Customer,
    "charges": stripe.Charge,
    "invoices": stripe.Invoice,
    "payment_intents": stripe.PaymentIntent,
    "prices": stripe.Price,
    "products": stripe.Product,
    "subscriptions": stripe.Subscription,
}
# Derived from _SEARCH_RESOURCE_MAP so the two never drift.
_SEARCHABLE = set(_SEARCH_RESOURCE_MAP)


def _get_api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY is not set. "
            "Get a restricted key at https://dashboard.stripe.com/apikeys"
        )
    return key


async def _stripe(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a sync Stripe SDK call in a thread so the event loop stays unblocked.

    api_key is passed per-call (not via the global stripe.api_key) to avoid
    a race condition when multiple tool calls execute concurrently.
    """
    key = _get_api_key()
    return await asyncio.to_thread(fn, *args, api_key=key, **kwargs)


def _obj(result: Any) -> str:
    """Convert a Stripe API object to a compact JSON string."""
    if hasattr(result, "to_dict"):
        return json.dumps(result.to_dict(), default=str)
    return json.dumps(result, default=str)


def _require(args: dict[str, Any], *keys: str) -> None:
    """Raise ValueError with a clear message for any missing or empty required key."""
    for k in keys:
        # Empty string is treated as missing — Stripe would reject it anyway.
        if not args.get(k):
            raise ValueError(f"Missing required field: '{k}'")


def _text(result: Any) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=_obj(result))])


def _err(exc: Exception) -> CallToolResult:
    # Sanitise AuthenticationError to avoid leaking partial response bodies.
    if isinstance(exc, stripe.error.AuthenticationError):
        msg = "Authentication failed — check STRIPE_SECRET_KEY"
    else:
        msg = str(exc)
    return CallToolResult(
        content=[TextContent(type="text", text=f"Error: {msg}")],
        isError=True,
    )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(tools=[
        # ── Account ──────────────────────────────────────────────────────────
        Tool(
            name="get_stripe_account_info",
            description="Retrieve the connected Stripe account details (name, country, currency, capabilities).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="retrieve_balance",
            description="Get the current Stripe account balance broken down by currency and fund type.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Customers ────────────────────────────────────────────────────────
        Tool(
            name="create_customer",
            description="Create a new Stripe customer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full name."},
                    "email": {"type": "string", "description": "Email address."},
                    "phone": {"type": "string"},
                    "description": {"type": "string"},
                    "metadata": {"type": "object", "description": "Key-value metadata."},
                },
            },
        ),
        Tool(
            name="list_customers",
            description="List Stripe customers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "email": {"type": "string", "description": "Filter by exact email."},
                    "starting_after": {"type": "string", "description": "Pagination cursor (customer ID)."},
                },
            },
        ),
        # ── Products ─────────────────────────────────────────────────────────
        Tool(
            name="create_product",
            description="Create a new Stripe product.",
            inputSchema={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "active": {"type": "boolean", "default": True},
                    "metadata": {"type": "object"},
                },
            },
        ),
        Tool(
            name="list_products",
            description="List Stripe products.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "active": {"type": "boolean"},
                    "starting_after": {"type": "string"},
                },
            },
        ),
        # ── Prices ───────────────────────────────────────────────────────────
        Tool(
            name="create_price",
            description="Create a price for a product.",
            inputSchema={
                "type": "object",
                "required": ["product", "unit_amount", "currency"],
                "properties": {
                    "product": {"type": "string", "description": "Product ID (prod_...)."},
                    "unit_amount": {"type": "integer", "description": "Amount in smallest currency unit (e.g. cents)."},
                    "currency": {"type": "string", "description": "ISO 4217 currency code (e.g. 'usd')."},
                    "recurring": {
                        "type": "object",
                        "description": "Recurring config — e.g. {\"interval\": \"month\"}.",
                        "properties": {
                            "interval": {"type": "string", "enum": ["day", "week", "month", "year"]},
                            "interval_count": {"type": "integer"},
                        },
                    },
                    "nickname": {"type": "string"},
                    "metadata": {"type": "object"},
                },
            },
        ),
        Tool(
            name="list_prices",
            description="List prices, optionally filtered by product.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "product": {"type": "string"},
                    "active": {"type": "boolean"},
                    "starting_after": {"type": "string"},
                },
            },
        ),
        # ── Payment Links ─────────────────────────────────────────────────────
        Tool(
            name="create_payment_link",
            description="Create a hosted payment link for a price.",
            inputSchema={
                "type": "object",
                "required": ["price_id", "quantity"],
                "properties": {
                    "price_id": {"type": "string", "description": "Price ID (price_...)."},
                    "quantity": {"type": "integer", "minimum": 1},
                    "after_completion": {
                        "type": "object",
                        "description": "What to show after payment — e.g. {\"type\": \"redirect\", \"redirect\": {\"url\": \"https://...\"}}.",
                    },
                    "metadata": {"type": "object"},
                },
            },
        ),
        # ── Payment Intents ───────────────────────────────────────────────────
        Tool(
            name="list_payment_intents",
            description="List PaymentIntents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "customer": {"type": "string", "description": "Filter by customer ID."},
                    "starting_after": {"type": "string"},
                },
            },
        ),
        # ── Invoices ──────────────────────────────────────────────────────────
        Tool(
            name="create_invoice",
            description="Create a draft invoice for a customer.",
            inputSchema={
                "type": "object",
                "required": ["customer"],
                "properties": {
                    "customer": {"type": "string", "description": "Customer ID (cus_...)."},
                    "auto_advance": {"type": "boolean", "default": False},
                    "collection_method": {
                        "type": "string",
                        "enum": ["charge_automatically", "send_invoice"],
                        "default": "send_invoice",
                    },
                    "description": {"type": "string"},
                    "metadata": {"type": "object"},
                },
            },
        ),
        Tool(
            name="create_invoice_item",
            description="Add a line item to a customer's upcoming invoice.",
            inputSchema={
                "type": "object",
                "required": ["customer"],
                "properties": {
                    "customer": {"type": "string"},
                    "price": {"type": "string", "description": "Price ID — use this OR amount+currency."},
                    "quantity": {"type": "integer", "default": 1},
                    "amount": {"type": "integer", "description": "Amount in smallest unit (alternative to price)."},
                    "currency": {"type": "string", "description": "Required if amount is set."},
                    "description": {"type": "string"},
                    "invoice": {"type": "string", "description": "Attach to a specific draft invoice ID."},
                    "metadata": {"type": "object"},
                },
            },
        ),
        Tool(
            name="finalize_invoice",
            description="Finalize a draft invoice so it can be sent or collected.",
            inputSchema={
                "type": "object",
                "required": ["invoice_id"],
                "properties": {
                    "invoice_id": {"type": "string", "description": "Invoice ID (in_...)."},
                    "auto_advance": {"type": "boolean"},
                },
            },
        ),
        Tool(
            name="list_invoices",
            description="List invoices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "customer": {"type": "string"},
                    "status": {"type": "string", "enum": ["draft", "open", "paid", "uncollectible", "void"]},
                    "starting_after": {"type": "string"},
                },
            },
        ),
        # ── Subscriptions ─────────────────────────────────────────────────────
        Tool(
            name="cancel_subscription",
            description="Cancel an active subscription immediately.",
            inputSchema={
                "type": "object",
                "required": ["subscription_id"],
                "properties": {
                    "subscription_id": {"type": "string", "description": "Subscription ID (sub_...)."},
                    "invoice_now": {"type": "boolean", "description": "Invoice any pending proration."},
                    "prorate": {"type": "boolean"},
                },
            },
        ),
        Tool(
            name="list_subscriptions",
            description="List subscriptions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "customer": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["active", "past_due", "unpaid", "canceled", "incomplete", "trialing", "all"],
                    },
                    "starting_after": {"type": "string"},
                },
            },
        ),
        Tool(
            name="update_subscription",
            description="Update an existing subscription (e.g. change plan, quantity, or metadata).",
            inputSchema={
                "type": "object",
                "required": ["subscription_id"],
                "properties": {
                    "subscription_id": {"type": "string"},
                    "items": {
                        "type": "array",
                        "description": "New line items — e.g. [{\"price\": \"price_...\", \"quantity\": 2}].",
                        "items": {"type": "object"},
                    },
                    "metadata": {"type": "object"},
                    "proration_behavior": {
                        "type": "string",
                        "enum": ["create_prorations", "none", "always_invoice"],
                    },
                },
            },
        ),
        # ── Refunds ───────────────────────────────────────────────────────────
        Tool(
            name="create_refund",
            description="Refund a charge or payment intent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "payment_intent": {"type": "string", "description": "PaymentIntent ID — use this OR charge."},
                    "charge": {"type": "string", "description": "Charge ID — use this OR payment_intent."},
                    "amount": {"type": "integer", "description": "Amount to refund in smallest unit. Omit to refund in full."},
                    "reason": {"type": "string", "enum": ["duplicate", "fraudulent", "requested_by_customer"]},
                    "metadata": {"type": "object"},
                },
            },
        ),
        # ── Coupons ───────────────────────────────────────────────────────────
        Tool(
            name="create_coupon",
            description="Create a discount coupon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "percent_off": {"type": "number", "description": "Percentage discount (0–100). Use this or amount_off."},
                    "amount_off": {"type": "integer", "description": "Fixed discount in smallest currency unit."},
                    "currency": {"type": "string", "description": "Required if amount_off is set."},
                    "duration": {"type": "string", "enum": ["forever", "once", "repeating"], "default": "once"},
                    "duration_in_months": {"type": "integer", "description": "Required if duration=repeating."},
                    "name": {"type": "string"},
                    "id": {"type": "string", "description": "Optional custom coupon code."},
                    "metadata": {"type": "object"},
                },
            },
        ),
        Tool(
            name="list_coupons",
            description="List coupons.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "starting_after": {"type": "string"},
                },
            },
        ),
        # ── Disputes ─────────────────────────────────────────────────────────
        Tool(
            name="list_disputes",
            description="List disputes (chargebacks).",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "charge": {"type": "string"},
                    "payment_intent": {"type": "string"},
                    "starting_after": {"type": "string"},
                },
            },
        ),
        Tool(
            name="update_dispute",
            description="Submit evidence or metadata for a dispute.",
            inputSchema={
                "type": "object",
                "required": ["dispute_id"],
                "properties": {
                    "dispute_id": {"type": "string", "description": "Dispute ID (dp_...)."},
                    "evidence": {
                        "type": "object",
                        "description": "Evidence fields — e.g. {\"customer_explanation\": \"...\"}.",
                    },
                    "metadata": {"type": "object"},
                    "submit": {"type": "boolean", "description": "Submit evidence to Stripe immediately."},
                },
            },
        ),
        # ── Search / Utility ─────────────────────────────────────────────────
        Tool(
            name="search_stripe_resources",
            description=(
                "Search Stripe resources using query syntax. "
                f"Supported resource_type values: {', '.join(sorted(_SEARCHABLE))}."
            ),
            inputSchema={
                "type": "object",
                "required": ["query", "resource_type"],
                "properties": {
                    "query": {"type": "string", "description": "Stripe search query — e.g. \"email:'alice@example.com'\"."},
                    "resource_type": {"type": "string", "enum": sorted(_SEARCHABLE)},
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                },
            },
        ),
        Tool(
            name="fetch_stripe_resources",
            description=(
                "Retrieve one or more Stripe objects by ID. "
                f"Supported resource_type values: {', '.join(sorted(_FETCHABLE))}."
            ),
            inputSchema={
                "type": "object",
                "required": ["resource_type", "ids"],
                "properties": {
                    "resource_type": {"type": "string", "enum": sorted(_FETCHABLE)},
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 20,
                    },
                },
            },
        ),
        Tool(
            name="search_stripe_documentation",
            description="Return a direct link to the Stripe documentation for a given query or topic.",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Topic or keyword to look up in Stripe docs."},
                },
            },
        ),
    ])


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    try:
        return await _dispatch(name, arguments)
    except Exception as exc:
        return _err(exc)


async def _dispatch(name: str, args: dict[str, Any]) -> CallToolResult:  # noqa: C901
    # ── Account ──────────────────────────────────────────────────────────────
    if name == "get_stripe_account_info":
        return _text(await _stripe(stripe.Account.retrieve))

    if name == "retrieve_balance":
        return _text(await _stripe(stripe.Balance.retrieve))

    # ── Customers ─────────────────────────────────────────────────────────────
    if name == "create_customer":
        params = _pick(args, "name", "email", "phone", "description", "metadata")
        return _text(await _stripe(stripe.Customer.create, **params))

    if name == "list_customers":
        params = _pick(args, "limit", "email", "starting_after")
        return _text(await _stripe(stripe.Customer.list, **params))

    # ── Products ──────────────────────────────────────────────────────────────
    if name == "create_product":
        params = _pick(args, "name", "description", "active", "metadata")
        return _text(await _stripe(stripe.Product.create, **params))

    if name == "list_products":
        params = _pick(args, "limit", "active", "starting_after")
        return _text(await _stripe(stripe.Product.list, **params))

    # ── Prices ────────────────────────────────────────────────────────────────
    if name == "create_price":
        params = _pick(args, "product", "unit_amount", "currency", "recurring", "nickname", "metadata")
        return _text(await _stripe(stripe.Price.create, **params))

    if name == "list_prices":
        params = _pick(args, "limit", "product", "active", "starting_after")
        return _text(await _stripe(stripe.Price.list, **params))

    # ── Payment Links ─────────────────────────────────────────────────────────
    if name == "create_payment_link":
        _require(args, "price_id", "quantity")
        line_items = [{"price": args["price_id"], "quantity": args["quantity"]}]  # tool uses price_id to avoid collision with the Stripe 'price' keyword
        extra = _pick(args, "after_completion", "metadata")
        return _text(await _stripe(stripe.PaymentLink.create, line_items=line_items, **extra))

    # ── Payment Intents ───────────────────────────────────────────────────────
    if name == "list_payment_intents":
        params = _pick(args, "limit", "customer", "starting_after")
        return _text(await _stripe(stripe.PaymentIntent.list, **params))

    # ── Invoices ──────────────────────────────────────────────────────────────
    if name == "create_invoice":
        params = _pick(args, "customer", "auto_advance", "collection_method", "description", "metadata")
        return _text(await _stripe(stripe.Invoice.create, **params))

    if name == "create_invoice_item":
        if args.get("amount") and not args.get("currency"):
            raise ValueError("'currency' is required when 'amount' is set.")
        params = _pick(args, "customer", "price", "quantity", "amount", "currency", "description", "invoice", "metadata")
        return _text(await _stripe(stripe.InvoiceItem.create, **params))

    if name == "finalize_invoice":
        _require(args, "invoice_id")
        invoice_id = args["invoice_id"]
        extra = _pick(args, "auto_advance")
        key = _get_api_key()

        def _finalize() -> Any:
            # Two Stripe calls must share the same thread and key snapshot so
            # the retrieve and finalize_invoice are atomic. Do NOT split into
            # two _stripe() calls — that would use two threads and two round-trips.
            inv = stripe.Invoice.retrieve(invoice_id, api_key=key)
            return inv.finalize_invoice(api_key=key, **extra)

        return _text(await asyncio.to_thread(_finalize))

    if name == "list_invoices":
        params = _pick(args, "limit", "customer", "status", "starting_after")
        return _text(await _stripe(stripe.Invoice.list, **params))

    # ── Subscriptions ─────────────────────────────────────────────────────────
    if name == "cancel_subscription":
        _require(args, "subscription_id")
        sub_id = args["subscription_id"]
        extra = _pick(args, "invoice_now", "prorate")
        return _text(await _stripe(stripe.Subscription.cancel, sub_id, **extra))

    if name == "list_subscriptions":
        params = _pick(args, "limit", "customer", "status", "starting_after")
        return _text(await _stripe(stripe.Subscription.list, **params))

    if name == "update_subscription":
        _require(args, "subscription_id")
        sub_id = args["subscription_id"]
        params = _pick(args, "items", "metadata", "proration_behavior")
        return _text(await _stripe(stripe.Subscription.modify, sub_id, **params))

    # ── Refunds ───────────────────────────────────────────────────────────────
    if name == "create_refund":
        if not args.get("payment_intent") and not args.get("charge"):
            raise ValueError("Either 'payment_intent' or 'charge' is required.")
        params = _pick(args, "payment_intent", "charge", "amount", "reason", "metadata")
        return _text(await _stripe(stripe.Refund.create, **params))

    # ── Coupons ───────────────────────────────────────────────────────────────
    if name == "create_coupon":
        if not args.get("percent_off") and not args.get("amount_off"):
            raise ValueError("Either 'percent_off' or 'amount_off' is required.")
        if args.get("amount_off") and not args.get("currency"):
            raise ValueError("'currency' is required when 'amount_off' is set.")
        if args.get("duration") == "repeating" and not args.get("duration_in_months"):
            raise ValueError("'duration_in_months' is required when duration='repeating'.")
        params = _pick(args, "percent_off", "amount_off", "currency", "duration",
                       "duration_in_months", "name", "id", "metadata")
        return _text(await _stripe(stripe.Coupon.create, **params))

    if name == "list_coupons":
        params = _pick(args, "limit", "starting_after")
        return _text(await _stripe(stripe.Coupon.list, **params))

    # ── Disputes ──────────────────────────────────────────────────────────────
    if name == "list_disputes":
        params = _pick(args, "limit", "charge", "payment_intent", "starting_after")
        return _text(await _stripe(stripe.Dispute.list, **params))

    if name == "update_dispute":
        _require(args, "dispute_id")
        dispute_id = args["dispute_id"]
        params = _pick(args, "evidence", "metadata", "submit")
        return _text(await _stripe(stripe.Dispute.modify, dispute_id, **params))

    # ── Search / Utility ──────────────────────────────────────────────────────
    if name == "search_stripe_resources":
        resource_type = args["resource_type"]
        if resource_type not in _SEARCHABLE:
            raise ValueError(f"Unsupported resource_type '{resource_type}'. Choose from: {', '.join(sorted(_SEARCHABLE))}")
        cls = _SEARCH_RESOURCE_MAP[resource_type]
        query = args["query"]
        limit = args.get("limit", 10)
        return _text(await _stripe(cls.search, query=query, limit=limit))

    if name == "fetch_stripe_resources":
        resource_type = args["resource_type"]
        if resource_type not in _FETCHABLE:
            raise ValueError(f"Unsupported resource_type '{resource_type}'.")
        cls = _FETCHABLE[resource_type]
        ids: list[str] = args["ids"][:20]  # enforce maxItems even if client skips schema validation
        raw = await asyncio.gather(*[_stripe(cls.retrieve, rid) for rid in ids], return_exceptions=True)
        results = []
        for rid, obj in zip(ids, raw):
            if isinstance(obj, stripe.error.AuthenticationError):
                results.append({"id": rid, "error": "Authentication failed — check STRIPE_SECRET_KEY"})
            elif isinstance(obj, Exception):
                results.append({"id": rid, "error": str(obj)})
            else:
                results.append(obj.to_dict() if hasattr(obj, "to_dict") else obj)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(results, default=str))]
        )

    if name == "search_stripe_documentation":
        query = args["query"]
        qs = urllib.parse.urlencode({"q": query})
        url = f"https://docs.stripe.com/search?{qs}"
        return CallToolResult(
            content=[TextContent(type="text", text=f"Stripe documentation search:\n{url}")]
        )

    return CallToolResult(
        content=[TextContent(type="text", text=f"Unknown tool: {name}")],
        isError=True,
    )


def _pick(args: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Return a dict of only the keys that are present in args (drops None/missing).

    False and 0 are preserved — they are intentional values for Stripe fields
    like auto_advance=False. Only None (meaning "not provided") is dropped.
    """
    return {k: args[k] for k in keys if k in args and args[k] is not None}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    asyncio.run(_run())


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    main()
