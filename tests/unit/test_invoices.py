"""Unit tests for create_invoice, create_invoice_item, finalize_invoice, list_invoices."""

from unittest.mock import MagicMock, patch

import stripe_mcp.server as srv
from tests.conftest import stripe_obj as _obj


def _invoice_obj(inv_id="in_abc") -> MagicMock:
    m = MagicMock()
    m.to_dict.return_value = {"id": inv_id, "status": "draft", "object": "invoice"}
    m.finalize_invoice.return_value = _obj({"id": inv_id, "status": "open", "object": "invoice"})
    return m


async def test_create_invoice_required_fields():
    fake = _obj({"id": "in_abc", "status": "draft", "object": "invoice"})
    with patch("stripe.Invoice.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_invoice", {"customer": "cus_123"})
    assert not result.isError
    assert "in_abc" in result.content[0].text
    assert mock_create.call_args.kwargs["customer"] == "cus_123"


async def test_create_invoice_collection_method():
    fake = _obj({"id": "in_def", "object": "invoice"})
    with patch("stripe.Invoice.create", return_value=fake) as mock_create:
        await srv.call_tool("create_invoice", {
            "customer": "cus_123",
            "collection_method": "charge_automatically",
            "auto_advance": True,
        })
    kwargs = mock_create.call_args.kwargs
    assert kwargs["collection_method"] == "charge_automatically"
    assert kwargs["auto_advance"] is True


async def test_create_invoice_item_with_price():
    fake = _obj({"id": "ii_abc", "object": "invoiceitem"})
    with patch("stripe.InvoiceItem.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_invoice_item", {
            "customer": "cus_123",
            "price": "price_abc",
            "quantity": 3,
        })
    assert not result.isError
    kwargs = mock_create.call_args.kwargs
    assert kwargs["customer"] == "cus_123"
    assert kwargs["price"] == "price_abc"
    assert kwargs["quantity"] == 3


async def test_create_invoice_item_with_amount():
    fake = _obj({"id": "ii_def", "object": "invoiceitem"})
    with patch("stripe.InvoiceItem.create", return_value=fake) as mock_create:
        await srv.call_tool("create_invoice_item", {
            "customer": "cus_123",
            "amount": 5000,
            "currency": "usd",
            "description": "Custom service",
        })
    kwargs = mock_create.call_args.kwargs
    assert kwargs["amount"] == 5000
    assert kwargs["currency"] == "usd"
    assert "price" not in kwargs


async def test_finalize_invoice_calls_retrieve_then_finalize():
    inv = _invoice_obj("in_abc")
    with patch("stripe.Invoice.retrieve", return_value=inv) as mock_retrieve:
        result = await srv.call_tool("finalize_invoice", {"invoice_id": "in_abc"})
    assert not result.isError
    assert mock_retrieve.call_args.args[0] == "in_abc"
    assert inv.finalize_invoice.call_count == 1


async def test_finalize_invoice_passes_auto_advance():
    inv = _invoice_obj("in_xyz")
    with patch("stripe.Invoice.retrieve", return_value=inv):
        await srv.call_tool("finalize_invoice", {"invoice_id": "in_xyz", "auto_advance": True})
    assert inv.finalize_invoice.call_args.kwargs.get("auto_advance") is True


async def test_list_invoices_status_filter():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Invoice.list", return_value=fake) as mock_list:
        await srv.call_tool("list_invoices", {"customer": "cus_123", "status": "paid", "limit": 20})
    kwargs = mock_list.call_args.kwargs
    assert kwargs["status"] == "paid"
    assert kwargs["customer"] == "cus_123"


async def test_create_invoice_item_amount_without_currency_returns_error():
    result = await srv.call_tool("create_invoice_item", {"customer": "cus_123", "amount": 500})
    assert result.isError
    assert "currency" in result.content[0].text


async def test_create_invoice_stripe_error():
    import stripe
    with patch("stripe.Invoice.create", side_effect=stripe.error.InvalidRequestError("No such customer", "customer")):
        result = await srv.call_tool("create_invoice", {"customer": "cus_bad"})
    assert result.isError
