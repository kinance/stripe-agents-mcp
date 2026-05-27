"""Unit tests for search_stripe_resources, fetch_stripe_resources, search_stripe_documentation."""

from unittest.mock import patch

import stripe_mcp.server as srv
from tests.conftest import stripe_obj as _obj


def _fetchable_obj(rid: str, kind: str):
    return _obj({"id": rid, "object": kind})


# ── search_stripe_resources ──────────────────────────────────────────────────

async def test_search_customers():
    fake = _obj({"object": "search_result", "data": [], "url": "/v1/customers/search"})
    with patch("stripe.Customer.search", return_value=fake) as mock_search:
        result = await srv.call_tool("search_stripe_resources", {
            "query": "email:'alice@example.com'",
            "resource_type": "customers",
            "limit": 5,
        })
    assert not result.isError
    assert mock_search.call_args.kwargs["query"] == "email:'alice@example.com'"
    assert mock_search.call_args.kwargs["limit"] == 5


async def test_search_invoices():
    fake = _obj({"object": "search_result", "data": []})
    with patch("stripe.Invoice.search", return_value=fake) as mock_search:
        await srv.call_tool("search_stripe_resources", {
            "query": "status:'open'",
            "resource_type": "invoices",
        })
    mock_search.assert_called_once()


async def test_search_unsupported_resource_type():
    result = await srv.call_tool("search_stripe_resources", {
        "query": "anything",
        "resource_type": "refunds",  # not in _SEARCHABLE
    })
    assert result.isError
    assert "Unsupported resource_type" in result.content[0].text


async def test_search_payment_intents():
    fake = _obj({"object": "search_result", "data": []})
    with patch("stripe.PaymentIntent.search", return_value=fake):
        result = await srv.call_tool("search_stripe_resources", {
            "query": "status:'requires_payment_method'",
            "resource_type": "payment_intents",
        })
    assert not result.isError


# ── fetch_stripe_resources ────────────────────────────────────────────────────

async def test_fetch_single_customer():
    fake = _fetchable_obj("cus_abc", "customer")
    with patch("stripe.Customer.retrieve", return_value=fake) as mock_retrieve:
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "customer",
            "ids": ["cus_abc"],
        })
    assert not result.isError
    assert "cus_abc" in result.content[0].text
    assert mock_retrieve.call_args.args[0] == "cus_abc"


async def test_fetch_multiple_products():
    fake_a = _fetchable_obj("prod_aaa", "product")
    fake_b = _fetchable_obj("prod_bbb", "product")
    with patch("stripe.Product.retrieve", side_effect=[fake_a, fake_b]) as mock_retrieve:
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "product",
            "ids": ["prod_aaa", "prod_bbb"],
        })
    assert not result.isError
    text = result.content[0].text
    assert "prod_aaa" in text
    assert "prod_bbb" in text
    # Both IDs fetched (gather runs them concurrently but mock side_effect is consumed in order)
    assert mock_retrieve.call_count == 2


async def test_fetch_unsupported_resource_type():
    result = await srv.call_tool("fetch_stripe_resources", {
        "resource_type": "balance",  # not in _FETCHABLE
        "ids": ["anything"],
    })
    assert result.isError
    assert "Unsupported resource_type" in result.content[0].text


async def test_fetch_partial_failure_returns_error_per_id():
    """One bad ID must not abort the whole batch — partial results returned with error annotation."""
    import stripe
    good = _fetchable_obj("prod_good", "product")
    with patch("stripe.Product.retrieve", side_effect=[
        good,
        stripe.error.InvalidRequestError("No such product", "id"),
    ]):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "product",
            "ids": ["prod_good", "prod_bad"],
        })
    assert not result.isError  # tool itself succeeds
    text = result.content[0].text
    assert "prod_good" in text
    assert "error" in text  # bad ID annotated with error key


async def test_fetch_auth_error_is_sanitised_in_batch():
    """AuthenticationError in gather path must not leak raw Stripe response body."""
    import stripe
    with patch("stripe.Customer.retrieve", side_effect=stripe.error.AuthenticationError("req_xyz secret")):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "customer",
            "ids": ["cus_any"],
        })
    assert not result.isError
    text = result.content[0].text
    assert "req_xyz" not in text
    assert "check STRIPE_SECRET_KEY" in text


async def test_fetch_invoice():
    fake = _fetchable_obj("in_abc", "invoice")
    with patch("stripe.Invoice.retrieve", return_value=fake):
        result = await srv.call_tool("fetch_stripe_resources", {
            "resource_type": "invoice",
            "ids": ["in_abc"],
        })
    assert not result.isError


# ── search_stripe_documentation ──────────────────────────────────────────────

async def test_search_docs_returns_url():
    result = await srv.call_tool("search_stripe_documentation", {"query": "payment intents"})
    assert not result.isError
    text = result.content[0].text
    assert "docs.stripe.com" in text
    assert "payment" in text.lower()


async def test_search_docs_percent_encodes_special_chars():
    """URL must be safe — special chars in query must be percent-encoded, not passed raw."""
    result = await srv.call_tool("search_stripe_documentation", {"query": "foo&evil=1"})
    text = result.content[0].text
    # The raw '&' must not appear as a bare query parameter separator
    assert "evil=1" not in text.split("?", 1)[-1].split("q=", 1)[-1].split("&")[0]
    assert "docs.stripe.com" in text


async def test_search_docs_never_errors():
    """Documentation search must never return isError — it's always a URL."""
    result = await srv.call_tool("search_stripe_documentation", {"query": "some obscure topic"})
    assert not result.isError
