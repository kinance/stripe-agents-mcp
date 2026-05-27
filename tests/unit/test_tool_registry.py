"""Verify tool count and names exposed by list_tools()."""

import stripe_mcp.server as srv


async def test_list_tools_count():
    result = await srv.list_tools()
    assert len(result.tools) == 25


async def test_tool_names():
    result = await srv.list_tools()
    names = {t.name for t in result.tools}
    expected = {
        "get_stripe_account_info",
        "retrieve_balance",
        "create_customer",
        "list_customers",
        "create_product",
        "list_products",
        "create_price",
        "list_prices",
        "create_payment_link",
        "list_payment_intents",
        "create_invoice",
        "create_invoice_item",
        "finalize_invoice",
        "list_invoices",
        "cancel_subscription",
        "list_subscriptions",
        "update_subscription",
        "create_refund",
        "create_coupon",
        "list_coupons",
        "list_disputes",
        "update_dispute",
        "search_stripe_resources",
        "fetch_stripe_resources",
        "search_stripe_documentation",
    }
    assert names == expected


async def test_all_tools_have_input_schema():
    result = await srv.list_tools()
    for tool in result.tools:
        assert tool.inputSchema is not None, f"{tool.name} missing inputSchema"
        assert tool.inputSchema.get("type") == "object", f"{tool.name} inputSchema type != object"


async def test_unknown_tool_returns_error():
    result = await srv.call_tool("does_not_exist", {})
    assert result.isError
    assert "Unknown tool" in result.content[0].text


async def test_missing_required_field_returns_clear_error():
    """create_payment_link without price_id should return a helpful error, not a KeyError."""
    result = await srv.call_tool("create_payment_link", {"quantity": 1})
    assert result.isError
    assert "price_id" in result.content[0].text


async def test_missing_invoice_id_returns_clear_error():
    result = await srv.call_tool("finalize_invoice", {})
    assert result.isError
    assert "invoice_id" in result.content[0].text
