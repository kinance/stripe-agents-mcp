"""Unit tests for get_stripe_account_info and retrieve_balance."""

from unittest.mock import patch

import stripe
import stripe_mcp.server as srv
from tests.conftest import stripe_obj as _mock_stripe_obj


async def test_get_stripe_account_info_returns_json():
    fake = _mock_stripe_obj({"id": "acct_123", "country": "US", "object": "account"})
    with patch("stripe.Account.retrieve", return_value=fake):
        result = await srv.call_tool("get_stripe_account_info", {})
    assert not result.isError
    text = result.content[0].text
    assert "acct_123" in text
    assert "US" in text


async def test_retrieve_balance_returns_json():
    fake = _mock_stripe_obj({
        "object": "balance",
        "available": [{"amount": 10000, "currency": "usd"}],
    })
    with patch("stripe.Balance.retrieve", return_value=fake):
        result = await srv.call_tool("retrieve_balance", {})
    assert not result.isError
    assert "10000" in result.content[0].text


async def test_get_account_info_propagates_stripe_error():
    with patch("stripe.Account.retrieve", side_effect=stripe.error.AuthenticationError("bad key")):
        result = await srv.call_tool("get_stripe_account_info", {})
    assert result.isError
    assert "Error" in result.content[0].text


async def test_auth_error_message_is_sanitised():
    """AuthenticationError must not echo the raw SDK message (may contain request IDs)."""
    with patch("stripe.Account.retrieve", side_effect=stripe.error.AuthenticationError("req_abc secret detail")):
        result = await srv.call_tool("get_stripe_account_info", {})
    assert result.isError
    assert "req_abc" not in result.content[0].text
    assert "check STRIPE_SECRET_KEY" in result.content[0].text


async def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    result = await srv.call_tool("get_stripe_account_info", {})
    assert result.isError
    assert "STRIPE_SECRET_KEY" in result.content[0].text
