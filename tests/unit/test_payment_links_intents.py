"""Unit tests for create_payment_link and list_payment_intents."""

from unittest.mock import patch

import stripe_mcp.server as srv
from tests.conftest import stripe_obj as _obj


# ── Payment Links ─────────────────────────────────────────────────────────────

async def test_create_payment_link_builds_line_items():
    fake = _obj({"id": "plink_abc", "url": "https://buy.stripe.com/test", "object": "payment_link"})
    with patch("stripe.PaymentLink.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_payment_link", {
            "price_id": "price_abc",
            "quantity": 2,
        })
    assert not result.isError
    assert "plink_abc" in result.content[0].text
    kwargs = mock_create.call_args.kwargs
    assert kwargs["line_items"] == [{"price": "price_abc", "quantity": 2}]


async def test_create_payment_link_with_after_completion():
    fake = _obj({"id": "plink_def", "object": "payment_link"})
    with patch("stripe.PaymentLink.create", return_value=fake) as mock_create:
        await srv.call_tool("create_payment_link", {
            "price_id": "price_xyz",
            "quantity": 1,
            "after_completion": {"type": "redirect", "redirect": {"url": "https://example.com/thanks"}},
        })
    kwargs = mock_create.call_args.kwargs
    assert kwargs["after_completion"]["type"] == "redirect"


async def test_create_payment_link_stripe_error():
    import stripe
    with patch("stripe.PaymentLink.create", side_effect=stripe.error.InvalidRequestError("bad price", "price")):
        result = await srv.call_tool("create_payment_link", {"price_id": "bad", "quantity": 1})
    assert result.isError


# ── Payment Intents ───────────────────────────────────────────────────────────

async def test_list_payment_intents_default():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.PaymentIntent.list", return_value=fake):
        result = await srv.call_tool("list_payment_intents", {})
    assert not result.isError


async def test_list_payment_intents_customer_filter():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.PaymentIntent.list", return_value=fake) as mock_list:
        await srv.call_tool("list_payment_intents", {"customer": "cus_abc", "limit": 5})
    assert mock_list.call_args.kwargs["customer"] == "cus_abc"
    assert mock_list.call_args.kwargs["limit"] == 5
