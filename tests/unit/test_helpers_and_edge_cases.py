"""
TDD tests for uncovered paths and edge cases.

Written RED first (describing expected behavior), then verified green.
"""

from unittest.mock import MagicMock, patch

import stripe
import stripe_mcp.server as srv
from tests.conftest import stripe_obj


# ---------------------------------------------------------------------------
# _obj — line 73: non-to_dict branch (currently uncovered)
# ---------------------------------------------------------------------------

async def test_get_account_info_with_plain_dict_response():
    """_obj must handle a raw dict result (no to_dict) — covers server.py:73."""
    # Simulate a Stripe API returning a plain dict instead of an SDK object
    plain = {"id": "acct_plain", "object": "account", "country": "JP"}
    with patch("stripe.Account.retrieve", return_value=plain):
        result = await srv.call_tool("get_stripe_account_info", {})
    assert not result.isError
    assert "acct_plain" in result.content[0].text


# ---------------------------------------------------------------------------
# _require — empty string treated as missing
# ---------------------------------------------------------------------------

async def test_require_rejects_empty_string_invoice_id():
    """`_require` must block empty string IDs — Stripe would reject '' with a confusing error."""
    result = await srv.call_tool("finalize_invoice", {"invoice_id": ""})
    assert result.isError
    assert "invoice_id" in result.content[0].text


async def test_require_rejects_empty_string_subscription_id():
    result = await srv.call_tool("cancel_subscription", {"subscription_id": ""})
    assert result.isError
    assert "subscription_id" in result.content[0].text


async def test_require_rejects_empty_string_dispute_id():
    result = await srv.call_tool("update_dispute", {"dispute_id": ""})
    assert result.isError
    assert "dispute_id" in result.content[0].text


# ---------------------------------------------------------------------------
# fetch_stripe_resources — ids[:20] cap
# ---------------------------------------------------------------------------

async def test_fetch_resources_caps_at_20_ids():
    """>20 IDs must be silently capped to 20 — server-side enforcement of maxItems."""
    fake = stripe_obj({"id": "prod_x", "object": "product"})
    with patch("stripe.Product.retrieve", return_value=fake) as mock_retrieve:
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "product",
            "ids": [f"prod_{i}" for i in range(25)],  # 25 IDs — 5 over cap
        })
    assert not result.isError
    # Only 20 retrieve calls must have been made
    assert mock_retrieve.call_count == 20


# ---------------------------------------------------------------------------
# create_refund — empty string payment_intent treated as missing
# ---------------------------------------------------------------------------

async def test_create_refund_with_empty_payment_intent_returns_error():
    result = await srv.call_tool("create_refund", {"payment_intent": ""})
    assert result.isError
    assert "payment_intent" in result.content[0].text or "charge" in result.content[0].text


# ---------------------------------------------------------------------------
# Pagination parameters — not previously exercised
# ---------------------------------------------------------------------------

async def test_list_invoices_starting_after():
    fake = stripe_obj({"object": "list", "data": []})
    with patch("stripe.Invoice.list", return_value=fake) as mock_list:
        await srv.call_tool("list_invoices", {"starting_after": "in_prev"})
    assert mock_list.call_args.kwargs["starting_after"] == "in_prev"


async def test_list_subscriptions_starting_after():
    fake = stripe_obj({"object": "list", "data": []})
    with patch("stripe.Subscription.list", return_value=fake) as mock_list:
        await srv.call_tool("list_subscriptions", {"starting_after": "sub_prev"})
    assert mock_list.call_args.kwargs["starting_after"] == "sub_prev"


async def test_list_payment_intents_starting_after():
    fake = stripe_obj({"object": "list", "data": []})
    with patch("stripe.PaymentIntent.list", return_value=fake) as mock_list:
        await srv.call_tool("list_payment_intents", {"starting_after": "pi_prev"})
    assert mock_list.call_args.kwargs["starting_after"] == "pi_prev"


async def test_list_prices_starting_after():
    fake = stripe_obj({"object": "list", "data": []})
    with patch("stripe.Price.list", return_value=fake) as mock_list:
        await srv.call_tool("list_prices", {"starting_after": "price_prev"})
    assert mock_list.call_args.kwargs["starting_after"] == "price_prev"


async def test_list_coupons_starting_after():
    fake = stripe_obj({"object": "list", "data": []})
    with patch("stripe.Coupon.list", return_value=fake) as mock_list:
        await srv.call_tool("list_coupons", {"starting_after": "coupon_prev"})
    assert mock_list.call_args.kwargs["starting_after"] == "coupon_prev"


async def test_list_disputes_starting_after():
    fake = stripe_obj({"object": "list", "data": []})
    with patch("stripe.Dispute.list", return_value=fake) as mock_list:
        await srv.call_tool("list_disputes", {"starting_after": "dp_prev"})
    assert mock_list.call_args.kwargs["starting_after"] == "dp_prev"


async def test_list_disputes_payment_intent_filter():
    fake = stripe_obj({"object": "list", "data": []})
    with patch("stripe.Dispute.list", return_value=fake) as mock_list:
        await srv.call_tool("list_disputes", {"payment_intent": "pi_abc"})
    assert mock_list.call_args.kwargs["payment_intent"] == "pi_abc"


# ---------------------------------------------------------------------------
# Untested fetch resource types
# ---------------------------------------------------------------------------

async def test_fetch_subscription():
    fake = stripe_obj({"id": "sub_abc", "object": "subscription"})
    with patch("stripe.Subscription.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "subscription",
            "ids": ["sub_abc"],
        })
    assert not result.isError
    assert "sub_abc" in result.content[0].text


async def test_fetch_price():
    fake = stripe_obj({"id": "price_abc", "object": "price"})
    with patch("stripe.Price.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "price",
            "ids": ["price_abc"],
        })
    assert not result.isError
    assert "price_abc" in result.content[0].text


async def test_fetch_coupon():
    fake = stripe_obj({"id": "COUP10", "object": "coupon"})
    with patch("stripe.Coupon.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "coupon",
            "ids": ["COUP10"],
        })
    assert not result.isError
    assert "COUP10" in result.content[0].text


async def test_fetch_refund():
    fake = stripe_obj({"id": "re_abc", "object": "refund"})
    with patch("stripe.Refund.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "refund",
            "ids": ["re_abc"],
        })
    assert not result.isError


async def test_fetch_payment_intent():
    fake = stripe_obj({"id": "pi_abc", "object": "payment_intent"})
    with patch("stripe.PaymentIntent.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "payment_intent",
            "ids": ["pi_abc"],
        })
    assert not result.isError


async def test_fetch_payment_link():
    fake = stripe_obj({"id": "plink_abc", "object": "payment_link"})
    with patch("stripe.PaymentLink.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "payment_link",
            "ids": ["plink_abc"],
        })
    assert not result.isError


async def test_fetch_dispute():
    fake = stripe_obj({"id": "dp_abc", "object": "dispute"})
    with patch("stripe.Dispute.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "dispute",
            "ids": ["dp_abc"],
        })
    assert not result.isError


# ---------------------------------------------------------------------------
# Untested search resource types
# ---------------------------------------------------------------------------

async def test_search_subscriptions():
    fake = stripe_obj({"object": "search_result", "data": []})
    with patch("stripe.Subscription.search", return_value=fake):
        result = await srv.call_tool("search_stripe_resources", {
            "query": "status:'active'",
            "resource_type": "subscriptions",
        })
    assert not result.isError


async def test_search_products():
    fake = stripe_obj({"object": "search_result", "data": []})
    with patch("stripe.Product.search", return_value=fake):
        result = await srv.call_tool("search_stripe_resources", {
            "query": "active:'true'",
            "resource_type": "products",
        })
    assert not result.isError


async def test_search_prices():
    fake = stripe_obj({"object": "search_result", "data": []})
    with patch("stripe.Price.search", return_value=fake):
        result = await srv.call_tool("search_stripe_resources", {
            "query": "currency:'usd'",
            "resource_type": "prices",
        })
    assert not result.isError


async def test_search_charges():
    fake = stripe_obj({"object": "search_result", "data": []})
    with patch("stripe.Charge.search", return_value=fake):
        result = await srv.call_tool("search_stripe_resources", {
            "query": "amount:>1000",
            "resource_type": "charges",
        })
    assert not result.isError


# ---------------------------------------------------------------------------
# create_invoice_item — invoice attachment
# ---------------------------------------------------------------------------

async def test_create_invoice_item_attached_to_invoice():
    fake = stripe_obj({"id": "ii_abc", "object": "invoiceitem"})
    with patch("stripe.InvoiceItem.create", return_value=fake) as mock_create:
        await srv.call_tool("create_invoice_item", {
            "customer": "cus_123",
            "price": "price_abc",
            "invoice": "in_abc",
        })
    assert mock_create.call_args.kwargs["invoice"] == "in_abc"


# ---------------------------------------------------------------------------
# create_product — metadata
# ---------------------------------------------------------------------------

async def test_create_product_with_metadata():
    fake = stripe_obj({"id": "prod_123", "object": "product"})
    with patch("stripe.Product.create", return_value=fake) as mock_create:
        await srv.call_tool("create_product", {
            "name": "Widget",
            "metadata": {"sku": "WGT-001"},
        })
    assert mock_create.call_args.kwargs["metadata"] == {"sku": "WGT-001"}


# ---------------------------------------------------------------------------
# update_dispute — metadata only (no evidence)
# ---------------------------------------------------------------------------

async def test_update_dispute_metadata_only():
    fake = stripe_obj({"id": "dp_abc", "object": "dispute"})
    with patch("stripe.Dispute.modify", return_value=fake) as mock_modify:
        await srv.call_tool("update_dispute", {
            "dispute_id": "dp_abc",
            "metadata": {"case_ref": "CR-2026-001"},
        })
    assert mock_modify.call_args.kwargs["metadata"] == {"case_ref": "CR-2026-001"}
    assert "evidence" not in mock_modify.call_args.kwargs
