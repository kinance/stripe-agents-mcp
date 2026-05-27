"""
E2E tests for stripe-agents-mcp.

These tests exercise the full MCP JSON-RPC protocol stack using in-process
in-memory streams. The server and client communicate via anyio MemoryObject
streams — identical to stdio transport except no subprocess boundary — so all
Stripe SDK calls are still mockable at the module level.

Coverage:
  - MCP initialize handshake
  - tools/list returns all 25 tools with correct metadata
  - tools/call round-trips for one tool per domain
  - tools/call error propagation (Stripe SDK raises → isError in response)
  - tools/call unknown tool handling
"""

from unittest.mock import MagicMock, patch

import anyio
import pytest

# ── Helpers ──────────────────────────────────────────────────────────────────

def _stripe_obj(data: dict) -> MagicMock:
    m = MagicMock()
    m.to_dict.return_value = data
    return m


async def _run_session(fn):
    """
    Wire the server and a client together via in-memory anyio streams, run
    `fn(session)` against the live server, then cancel.
    """
    from mcp.client.session import ClientSession
    from mcp.server.stdio import stdio_server
    import stripe_mcp.server as srv

    # Create two pairs of uni-directional byte streams.
    # server reads from client_to_server, writes to server_to_client.
    server_to_client_w, server_to_client_r = anyio.create_memory_object_stream(100)
    client_to_server_w, client_to_server_r = anyio.create_memory_object_stream(100)

    init_opts = srv.app.create_initialization_options()

    async with anyio.create_task_group() as tg:
        tg.start_soon(
            srv.app.run,
            client_to_server_r,
            server_to_client_w,
            init_opts,
        )
        async with ClientSession(server_to_client_r, client_to_server_w) as session:
            await session.initialize()
            await fn(session)
            tg.cancel_scope.cancel()


# ── Handshake ─────────────────────────────────────────────────────────────────

async def test_e2e_initialize_succeeds():
    """Server accepts the MCP initialize handshake."""
    async def check(session):
        # initialize() succeeded if we reach this line without exception
        pass
    await _run_session(check)


# ── tools/list ────────────────────────────────────────────────────────────────

async def test_e2e_list_tools_count():
    async def check(session):
        result = await session.list_tools()
        assert len(result.tools) == 25

    await _run_session(check)


async def test_e2e_list_tools_names():
    async def check(session):
        result = await session.list_tools()
        names = {t.name for t in result.tools}
        assert "create_customer" in names
        assert "create_payment_link" in names
        assert "search_stripe_resources" in names
        assert "finalize_invoice" in names

    await _run_session(check)


async def test_e2e_all_tools_have_description():
    async def check(session):
        result = await session.list_tools()
        for tool in result.tools:
            assert tool.description, f"{tool.name} has no description"

    await _run_session(check)


# ── tools/call — one per domain ──────────────────────────────────────────────

async def test_e2e_get_stripe_account_info():
    fake = _stripe_obj({"id": "acct_e2e", "country": "JP", "object": "account"})
    with patch("stripe.Account.retrieve", return_value=fake):
        async def check(session):
            result = await session.call_tool("get_stripe_account_info", {})
            assert not result.isError
            assert "acct_e2e" in result.content[0].text

        await _run_session(check)


async def test_e2e_retrieve_balance():
    fake = _stripe_obj({"object": "balance", "available": [{"amount": 50000, "currency": "usd"}]})
    with patch("stripe.Balance.retrieve", return_value=fake):
        async def check(session):
            result = await session.call_tool("retrieve_balance", {})
            assert not result.isError
            assert "50000" in result.content[0].text

        await _run_session(check)


async def test_e2e_create_customer():
    fake = _stripe_obj({"id": "cus_e2e", "name": "E2E User", "object": "customer"})
    with patch("stripe.Customer.create", return_value=fake):
        async def check(session):
            result = await session.call_tool("create_customer", {
                "name": "E2E User",
                "email": "e2e@example.com",
            })
            assert not result.isError
            assert "cus_e2e" in result.content[0].text

        await _run_session(check)


async def test_e2e_list_customers():
    fake = _stripe_obj({"object": "list", "data": [{"id": "cus_e2e", "object": "customer"}]})
    with patch("stripe.Customer.list", return_value=fake):
        async def check(session):
            result = await session.call_tool("list_customers", {"limit": 5})
            assert not result.isError

        await _run_session(check)


async def test_e2e_create_product():
    fake = _stripe_obj({"id": "prod_e2e", "name": "E2E Widget", "object": "product"})
    with patch("stripe.Product.create", return_value=fake):
        async def check(session):
            result = await session.call_tool("create_product", {"name": "E2E Widget"})
            assert not result.isError
            assert "prod_e2e" in result.content[0].text

        await _run_session(check)


async def test_e2e_create_price():
    fake = _stripe_obj({"id": "price_e2e", "unit_amount": 1999, "currency": "usd", "object": "price"})
    with patch("stripe.Price.create", return_value=fake):
        async def check(session):
            result = await session.call_tool("create_price", {
                "product": "prod_e2e",
                "unit_amount": 1999,
                "currency": "usd",
            })
            assert not result.isError
            assert "price_e2e" in result.content[0].text

        await _run_session(check)


async def test_e2e_create_payment_link():
    fake = _stripe_obj({"id": "plink_e2e", "url": "https://buy.stripe.com/e2e", "object": "payment_link"})
    with patch("stripe.PaymentLink.create", return_value=fake):
        async def check(session):
            result = await session.call_tool("create_payment_link", {
                "price_id": "price_e2e",
                "quantity": 1,
            })
            assert not result.isError
            assert "plink_e2e" in result.content[0].text

        await _run_session(check)


async def test_e2e_create_invoice_and_finalize():
    fake_create = _stripe_obj({"id": "in_e2e", "status": "draft", "object": "invoice"})
    fake_invoice = MagicMock()
    fake_invoice.to_dict.return_value = {"id": "in_e2e", "status": "open", "object": "invoice"}
    fake_invoice.finalize_invoice.return_value = fake_invoice

    with patch("stripe.Invoice.create", return_value=fake_create), \
         patch("stripe.Invoice.retrieve", return_value=fake_invoice):
        async def check(session):
            r1 = await session.call_tool("create_invoice", {"customer": "cus_e2e"})
            assert not r1.isError
            r2 = await session.call_tool("finalize_invoice", {"invoice_id": "in_e2e"})
            assert not r2.isError

        await _run_session(check)


async def test_e2e_cancel_subscription():
    fake = _stripe_obj({"id": "sub_e2e", "status": "canceled", "object": "subscription"})
    with patch("stripe.Subscription.cancel", return_value=fake):
        async def check(session):
            result = await session.call_tool("cancel_subscription", {"subscription_id": "sub_e2e"})
            assert not result.isError

        await _run_session(check)


async def test_e2e_create_refund():
    fake = _stripe_obj({"id": "re_e2e", "status": "succeeded", "object": "refund"})
    with patch("stripe.Refund.create", return_value=fake):
        async def check(session):
            result = await session.call_tool("create_refund", {"payment_intent": "pi_e2e"})
            assert not result.isError

        await _run_session(check)


async def test_e2e_create_coupon():
    fake = _stripe_obj({"id": "E2ECOUPON", "percent_off": 15.0, "object": "coupon"})
    with patch("stripe.Coupon.create", return_value=fake):
        async def check(session):
            result = await session.call_tool("create_coupon", {
                "percent_off": 15.0,
                "duration": "once",
            })
            assert not result.isError

        await _run_session(check)


async def test_e2e_search_stripe_resources():
    fake = _stripe_obj({"object": "search_result", "data": []})
    with patch("stripe.Customer.search", return_value=fake):
        async def check(session):
            result = await session.call_tool("search_stripe_resources", {
                "query": "email:'e2e@example.com'",
                "resource_type": "customers",
            })
            assert not result.isError

        await _run_session(check)


async def test_e2e_search_stripe_documentation():
    async def check(session):
        result = await session.call_tool("search_stripe_documentation", {"query": "webhooks"})
        assert not result.isError
        assert "docs.stripe.com" in result.content[0].text

    await _run_session(check)


# ── Error propagation ─────────────────────────────────────────────────────────

async def test_e2e_stripe_error_returns_is_error():
    """A Stripe API error in a tool must return isError=True through the full MCP stack."""
    import stripe

    with patch("stripe.Customer.create", side_effect=stripe.error.AuthenticationError("invalid key")):
        async def check(session):
            result = await session.call_tool("create_customer", {"email": "x@test.com"})
            assert result.isError

        await _run_session(check)


async def test_e2e_unknown_tool_is_error():
    async def check(session):
        result = await session.call_tool("nonexistent_tool", {})
        assert result.isError

    await _run_session(check)


async def test_e2e_search_unsupported_resource_type_is_error():
    async def check(session):
        result = await session.call_tool("search_stripe_resources", {
            "query": "anything",
            "resource_type": "refunds",
        })
        assert result.isError

    await _run_session(check)
