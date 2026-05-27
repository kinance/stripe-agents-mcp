"""Unit tests for cancel_subscription, list_subscriptions, update_subscription."""

from unittest.mock import patch

import stripe_mcp.server as srv
from tests.conftest import stripe_obj as _obj


async def test_cancel_subscription():
    fake = _obj({"id": "sub_abc", "status": "canceled", "object": "subscription"})
    with patch("stripe.Subscription.cancel", return_value=fake) as mock_cancel:
        result = await srv.call_tool("cancel_subscription", {"subscription_id": "sub_abc"})
    assert not result.isError
    assert "sub_abc" in result.content[0].text
    assert mock_cancel.call_args.args[0] == "sub_abc"


async def test_cancel_subscription_with_invoice_now():
    fake = _obj({"id": "sub_abc", "status": "canceled"})
    with patch("stripe.Subscription.cancel", return_value=fake) as mock_cancel:
        await srv.call_tool("cancel_subscription", {
            "subscription_id": "sub_abc",
            "invoice_now": True,
            "prorate": True,
        })
    kwargs = mock_cancel.call_args.kwargs
    assert kwargs["invoice_now"] is True
    assert kwargs["prorate"] is True


async def test_list_subscriptions_all_status():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Subscription.list", return_value=fake) as mock_list:
        await srv.call_tool("list_subscriptions", {"status": "all", "limit": 50})
    assert mock_list.call_args.kwargs["status"] == "all"


async def test_list_subscriptions_customer_filter():
    fake = _obj({"object": "list", "data": []})
    with patch("stripe.Subscription.list", return_value=fake) as mock_list:
        await srv.call_tool("list_subscriptions", {"customer": "cus_abc"})
    assert mock_list.call_args.kwargs["customer"] == "cus_abc"


async def test_update_subscription_items():
    fake = _obj({"id": "sub_abc", "status": "active", "object": "subscription"})
    with patch("stripe.Subscription.modify", return_value=fake) as mock_modify:
        result = await srv.call_tool("update_subscription", {
            "subscription_id": "sub_abc",
            "items": [{"price": "price_new", "quantity": 2}],
            "proration_behavior": "create_prorations",
        })
    assert not result.isError
    args = mock_modify.call_args
    assert args.args[0] == "sub_abc"
    assert args.kwargs["items"] == [{"price": "price_new", "quantity": 2}]
    assert args.kwargs["proration_behavior"] == "create_prorations"


async def test_update_subscription_metadata_only():
    fake = _obj({"id": "sub_abc", "object": "subscription"})
    with patch("stripe.Subscription.modify", return_value=fake) as mock_modify:
        await srv.call_tool("update_subscription", {
            "subscription_id": "sub_abc",
            "metadata": {"tier": "enterprise"},
        })
    kwargs = mock_modify.call_args.kwargs
    assert kwargs["metadata"] == {"tier": "enterprise"}
    assert "items" not in kwargs


async def test_cancel_subscription_stripe_error():
    import stripe
    with patch("stripe.Subscription.cancel", side_effect=stripe.error.InvalidRequestError("No such sub", "id")):
        result = await srv.call_tool("cancel_subscription", {"subscription_id": "sub_bad"})
    assert result.isError
