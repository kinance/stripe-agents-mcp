# stripe-agents-mcp

MCP server exposing 25 Stripe API tools for Claude and other MCP-compatible agents.

## Tools

| Category | Tools |
|---|---|
| Account | `get_stripe_account_info`, `retrieve_balance` |
| Customers | `create_customer`, `list_customers` |
| Products & Prices | `create_product`, `list_products`, `create_price`, `list_prices` |
| Payment Links | `create_payment_link` |
| Payment Intents | `list_payment_intents` |
| Invoices | `create_invoice`, `create_invoice_item`, `finalize_invoice`, `list_invoices` |
| Subscriptions | `cancel_subscription`, `list_subscriptions`, `update_subscription` |
| Refunds | `create_refund` |
| Coupons | `create_coupon`, `list_coupons` |
| Disputes | `list_disputes`, `update_dispute` |
| Utilities | `search_stripe_resources`, `fetch_stripe_resources`, `search_stripe_documentation` |

## Install via Claude Code

```
/plugin install stripe-agents-mcp@kinance
```

Then set your Stripe secret key in the environment where Claude Code runs:

```bash
export STRIPE_SECRET_KEY=sk_live_...
```

The plugin ships a `.mcp.json` that wires up the stdio server automatically — no manual config needed after install.

## Manual setup (Claude Desktop / other MCP clients)

```bash
pip install stripe-agents-mcp
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "stripe": {
      "command": "python",
      "args": ["-m", "stripe_mcp"],
      "env": {
        "STRIPE_SECRET_KEY": "sk_live_..."
      }
    }
  }
}
```

## Running directly

```bash
python -m stripe_mcp
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ --cov=stripe_mcp
```

## Security

- Pass a **restricted** Stripe key (`rk_*`) scoped to only the resources your agent needs.
- The server never logs or echoes the API key.
- All inputs are validated before reaching the Stripe SDK.
