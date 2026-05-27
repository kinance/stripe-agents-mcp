"""Shared fixtures and factories for stripe-agents-mcp tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def stripe_env(monkeypatch):
    """Ensure STRIPE_SECRET_KEY is always set for tests (value never reaches Stripe because
    all tests mock the SDK calls before any network I/O occurs)."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_unit")


def stripe_obj(data: dict) -> MagicMock:
    """Return a MagicMock that behaves like a Stripe SDK object with a given to_dict()."""
    m = MagicMock()
    m.to_dict.return_value = data
    return m
