"""Unit tests for create_refund, create_coupon, list_coupons, list_disputes, update_dispute."""

from unittest.mock import patch

import stripe_mcp.server as srv
from tests.conftest import stripe_obj as _obj


# ── Refunds ───────────────────────────────────────────────────────────────────

async def test_create_refund_by_payment_intent():
    fake = _obj({"id": "re_abc", "amount": 1000, "status": "succeeded", "object": "refund"})
    with patch("stripe.Refund.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_refund", {"payment_intent": "pi_abc"})
    assert not result.isError
    assert "re_abc" in result.content[0].text
    assert mock_create.call_args.kwargs["payment_intent"] == "pi_abc"


async def test_create_refund_partial_with_reason():
    fake = _obj({"id": "re_def", "amount": 500, "object": "refund"})
    with patch("stripe.Refund.create", return_value=fake) as mock_create:
        await srv.call_tool("create_refund", {
            "payment_intent": "pi_abc",
            "amount": 500,
            "reason": "requested_by_customer",
        })
    kwargs = mock_create.call_args.kwargs
    assert kwargs["amount"] == 500
    assert kwargs["reason"] == "requested_by_customer"


async def test_create_refund_by_charge():
    fake = _obj({"id": "re_ghi", "object": "refund"})
    with patch("stripe.Refund.create", return_value=fake) as mock_create:
        await srv.call_tool("create_refund", {"charge": "ch_abc"})
    assert "charge" in mock_create.call_args.kwargs


async def test_create_refund_without_payment_intent_or_charge_returns_error():
    result = await srv.call_tool("create_refund", {"amount": 500})
    assert result.isError
    assert "payment_intent" in result.content[0].text or "charge" in result.content[0].text


# ── Coupons ───────────────────────────────────────────────────────────────────

async def test_create_coupon_percent_off():
    fake = _obj({"id": "SUMMER20", "percent_off": 20.0, "duration": "once", "object": "coupon"})
    with patch("stripe.Coupon.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_coupon", {
            "percent_off": 20.0,
            "duration": "once",
            "name": "Summer Sale",
        })
    assert not result.isError
    kwargs = mock_create.call_args.kwargs
    assert kwargs["percent_off"] == 20.0
    assert kwargs["duration"] == "once"


async def test_create_coupon_amount_off():
    fake = _obj({"id": "FLAT500", "amount_off": 500, "currency": "usd", "object": "coupon"})
    with patch("stripe.Coupon.create", return_value=fake) as mock_create:
        await srv.call_tool("create_coupon", {
            "amount_off": 500,
            "currency": "usd",
            "duration": "forever",
        })
    kwargs = mock_create.call_args.kwargs
    assert kwargs["amount_off"] == 500
    assert kwargs["currency"] == "usd"


async def test_create_coupon_repeating():
    fake = _obj({"id": "REPEAT3", "duration": "repeating", "duration_in_months": 3, "object": "coupon"})
    with patch("stripe.Coupon.create", return_value=fake) as mock_create:
        await srv.call_tool("create_coupon", {
            "percent_off": 10.0,
            "duration": "repeating",
            "duration_in_months": 3,
        })
    kwargs = mock_create.call_args.kwargs
    assert kwargs["duration_in_months"] == 3


async def test_create_coupon_repeating_without_duration_in_months_returns_error():
    result = await srv.call_tool("create_coupon", {"percent_off": 10.0, "duration": "repeating"})
    assert result.isError
    assert "duration_in_months" in result.content[0].text


async def test_create_coupon_amount_off_without_currency_returns_error():
    result = await srv.call_tool("create_coupon", {"amount_off": 500, "duration": "once"})
    assert result.isError
    assert "currency" in result.content[0].text


async def test_create_coupon_neither_percent_nor_amount_returns_error():
    result = await srv.call_tool("create_coupon", {"duration": "once", "name": "Bad"})
    assert result.isError
    assert "percent_off" in result.content[0].text or "amount_off" in result.content[0].text


async def test_list_coupons():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Coupon.list", return_value=fake) as mock_list:
        result = await srv.call_tool("list_coupons", {"limit": 20})
    assert not result.isError
    assert mock_list.call_args.kwargs["limit"] == 20


# ── Disputes ─────────────────────────────────────────────────────────────────

async def test_list_disputes_default():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Dispute.list", return_value=fake):
        result = await srv.call_tool("list_disputes", {})
    assert not result.isError


async def test_list_disputes_charge_filter():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Dispute.list", return_value=fake) as mock_list:
        await srv.call_tool("list_disputes", {"charge": "ch_abc", "limit": 5})
    assert mock_list.call_args.kwargs["charge"] == "ch_abc"


async def test_update_dispute_with_evidence():
    fake = _obj({"id": "dp_abc", "status": "under_review", "object": "dispute"})
    with patch("stripe.Dispute.modify", return_value=fake) as mock_modify:
        result = await srv.call_tool("update_dispute", {
            "dispute_id": "dp_abc",
            "evidence": {"customer_explanation": "Customer received the item."},
            "submit": True,
        })
    assert not result.isError
    args = mock_modify.call_args
    assert args.args[0] == "dp_abc"
    assert args.kwargs["evidence"]["customer_explanation"] == "Customer received the item."
    assert args.kwargs["submit"] is True


async def test_update_dispute_stripe_error():
    import stripe
    with patch("stripe.Dispute.modify", side_effect=stripe.error.InvalidRequestError("No such dispute", "id")):
        result = await srv.call_tool("update_dispute", {"dispute_id": "dp_bad"})
    assert result.isError
