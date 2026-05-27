"""Unit tests for create_product, list_products, create_price, list_prices."""

from unittest.mock import patch

import stripe_mcp.server as srv
from tests.conftest import stripe_obj as _obj


# ── Products ─────────────────────────────────────────────────────────────────

async def test_create_product_required_fields():
    fake = _obj({"id": "prod_123", "name": "Widget", "object": "product"})
    with patch("stripe.Product.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_product", {"name": "Widget"})
    assert not result.isError
    assert "prod_123" in result.content[0].text
    assert mock_create.call_args.kwargs["name"] == "Widget"


async def test_create_product_with_description():
    fake = _obj({"id": "prod_456", "name": "Gadget"})
    with patch("stripe.Product.create", return_value=fake) as mock_create:
        await srv.call_tool("create_product", {"name": "Gadget", "description": "A gadget", "active": True})
    kwargs = mock_create.call_args.kwargs
    assert kwargs["description"] == "A gadget"
    assert kwargs["active"] is True


async def test_list_products_active_filter():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Product.list", return_value=fake) as mock_list:
        await srv.call_tool("list_products", {"active": True, "limit": 5})
    assert mock_list.call_args.kwargs["active"] is True
    assert mock_list.call_args.kwargs["limit"] == 5


async def test_list_products_no_args():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Product.list", return_value=fake):
        result = await srv.call_tool("list_products", {})
    assert not result.isError


# ── Prices ────────────────────────────────────────────────────────────────────

async def test_create_price_one_time():
    fake = _obj({"id": "price_abc", "unit_amount": 999, "currency": "usd", "object": "price"})
    with patch("stripe.Price.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_price", {
            "product": "prod_123",
            "unit_amount": 999,
            "currency": "usd",
        })
    assert not result.isError
    assert "price_abc" in result.content[0].text
    kwargs = mock_create.call_args.kwargs
    assert kwargs["product"] == "prod_123"
    assert kwargs["unit_amount"] == 999
    assert kwargs["currency"] == "usd"


async def test_create_price_recurring():
    fake = _obj({"id": "price_sub", "object": "price"})
    with patch("stripe.Price.create", return_value=fake) as mock_create:
        await srv.call_tool("create_price", {
            "product": "prod_123",
            "unit_amount": 2000,
            "currency": "usd",
            "recurring": {"interval": "month"},
        })
    kwargs = mock_create.call_args.kwargs
    assert kwargs["recurring"] == {"interval": "month"}


async def test_list_prices_product_filter():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Price.list", return_value=fake) as mock_list:
        await srv.call_tool("list_prices", {"product": "prod_123", "active": True})
    assert mock_list.call_args.kwargs["product"] == "prod_123"


async def test_create_price_error():
    import stripe
    with patch("stripe.Price.create", side_effect=stripe.error.InvalidRequestError("No such product", "product")):
        result = await srv.call_tool("create_price", {"product": "bad", "unit_amount": 100, "currency": "usd"})
    assert result.isError
