"""Unit tests for create_customer and list_customers."""

from unittest.mock import MagicMock, patch

import stripe_mcp.server as srv
from tests.conftest import stripe_obj


def _customer(cid="cus_abc", name="Alice", email="alice@example.com") -> MagicMock:
    return stripe_obj({"id": cid, "name": name, "email": email, "object": "customer"})


def _list_resp(customers: list) -> MagicMock:
    return stripe_obj({"object": "list", "data": [c.to_dict() for c in customers]})


async def test_create_customer_minimal():
    fake = _customer()
    with patch("stripe.Customer.create", return_value=fake) as mock_create:
        result = await srv.call_tool("create_customer", {"name": "Alice", "email": "alice@example.com"})
    assert not result.isError
    assert "cus_abc" in result.content[0].text
    assert mock_create.call_count == 1
    kwargs = mock_create.call_args.kwargs
    assert kwargs["name"] == "Alice"
    assert kwargs["email"] == "alice@example.com"


async def test_create_customer_with_phone_and_metadata():
    fake = _customer()
    with patch("stripe.Customer.create", return_value=fake) as mock_create:
        await srv.call_tool("create_customer", {
            "name": "Bob",
            "email": "bob@example.com",
            "phone": "+1234567890",
            "metadata": {"plan": "pro"},
        })
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["phone"] == "+1234567890"
    assert call_kwargs["metadata"] == {"plan": "pro"}


async def test_create_customer_without_optional_fields_omits_them():
    fake = _customer()
    with patch("stripe.Customer.create", return_value=fake) as mock_create:
        await srv.call_tool("create_customer", {"email": "x@example.com"})
    call_kwargs = mock_create.call_args.kwargs
    assert "phone" not in call_kwargs
    assert "metadata" not in call_kwargs


async def test_list_customers_default_limit():
    fake = _list_resp([_customer()])
    with patch("stripe.Customer.list", return_value=fake) as mock_list:
        result = await srv.call_tool("list_customers", {})
    assert not result.isError
    # _pick drops None/missing — limit not in args so it must not appear in the SDK call
    assert "limit" not in mock_list.call_args.kwargs


async def test_list_customers_with_email_filter():
    fake = _list_resp([_customer()])
    with patch("stripe.Customer.list", return_value=fake) as mock_list:
        await srv.call_tool("list_customers", {"email": "alice@example.com", "limit": 5})
    assert mock_list.call_args.kwargs["email"] == "alice@example.com"
    assert mock_list.call_args.kwargs["limit"] == 5


async def test_list_customers_pagination():
    fake = _list_resp([_customer("cus_page2")])
    with patch("stripe.Customer.list", return_value=fake) as mock_list:
        await srv.call_tool("list_customers", {"starting_after": "cus_abc"})
    assert mock_list.call_args.kwargs["starting_after"] == "cus_abc"


async def test_create_customer_stripe_error_returns_error_result():
    import stripe
    with patch("stripe.Customer.create", side_effect=stripe.error.InvalidRequestError("bad", "email")):
        result = await srv.call_tool("create_customer", {"email": "bad"})
    assert result.isError
