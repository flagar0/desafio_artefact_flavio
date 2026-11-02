"""MCP server exposing the store data/policies as tools (stdio transport).

Run standalone for inspection:  python -m app.mcp_server.server
The agent spawns it as a subprocess and talks MCP over stdio.

Tool names/descriptions are in English (models follow tool schemas better that way),
but tool *results* are in PT-BR and the agent is instructed to always answer in Portuguese.
"""
from typing import Literal

from mcp.server.fastmcp import FastMCP

from app import repository as repo

mcp = FastMCP("emporio-da-musica")

PolicyTopic = Literal[
    "about_and_contact", "opening_hours", "payment", "returns_exchanges",
    "shipping", "promotions", "special_situations", "warranty", "privacy",
]


@mcp.tool()
def search_products(
    query: str = "",
    max_price: float | None = None,
    min_price: float | None = None,
    only_available: bool = True,
) -> dict:
    """Search the product catalog. Use for any question about instruments, prices or availability by category/brand/budget.

    Args:
        query: free text, e.g. "violao", "guitarra yamaha", "ukulele soprano". Empty = all products.
        max_price: maximum FINAL price in BRL (promotion already applied), e.g. 1000.
        min_price: minimum FINAL price in BRL.
        only_available: True hides out-of-stock/discontinued items. Use False only if the customer asks about a specific unavailable product.
    Returns up to 8 products sorted by price, with original/final price, active promotion, PIX price and availability.
    """
    return repo.search_products(query, max_price, min_price, only_available)


@mcp.tool()
def get_product_details(name_or_id: str) -> dict:
    """Get full details (price, promotion, stock, specs, installments) of ONE specific product.
    Use when the customer names a model (e.g. "Takamine GD20"). If the product is unavailable,
    the result already contains similar alternatives to suggest.

    Args:
        name_or_id: product name (partial is fine) or numeric product_id.
    """
    return repo.get_product(name_or_id)


@mcp.tool()
def list_categories() -> list[dict]:
    """List the product categories the store sells (with number of active products)."""
    return repo.list_categories()


@mcp.tool()
def get_customer_orders(customer_id: int, order_id: int | None = None) -> dict:
    """Get the orders of the customer currently chatting: status, items, tracking code, delivery estimate
    and (for delivered orders) whether return/exchange/warranty deadlines are still valid.
    Use for order status, tracking, returns and cancellations. The customer_id is the one given in the system prompt.

    Args:
        customer_id: id of the current customer (from the system prompt).
        order_id: optional, filter a single order.
    """
    return repo.get_orders(customer_id, order_id)


@mcp.tool()
def get_store_policies(topic: PolicyTopic) -> dict:
    """Read the official store policy for a topic. Use for rules, NOT for prices/stock/orders.

    Topics: about_and_contact (address, phone, WhatsApp, e-mail, what the store does NOT sell),
    opening_hours, payment (PIX, card, installments), returns_exchanges (arrependimento, defeito, troca),
    shipping (frete, prazos, rastreio), promotions (rules), special_situations (out of stock, complaint...),
    warranty, privacy (LGPD).
    """
    return repo.get_policy(topic)


@mcp.tool()
def get_opening_status() -> dict:
    """Tell if the store is open RIGHT NOW, today's hours and the next opening time. Use for 'are you open?' questions."""
    return repo.opening_status()


if __name__ == "__main__":
    mcp.run(transport="stdio")
