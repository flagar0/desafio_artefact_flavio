"""Deterministic tests for the data layer (no LLM involved)."""
import pytest

from app import repository as repo
from app.ingest import build_database


@pytest.fixture(scope="session", autouse=True)
def _db():
    build_database()


def _set_now(monkeypatch, iso: str):
    monkeypatch.setattr(repo, "FAKE_NOW", iso)


def test_search_respects_budget_and_availability():
    res = repo.search_products("violao", max_price=1000)
    assert res["total_found"] > 0
    assert all(p["available"] for p in res["showing"])
    assert all(repo._price_now(p) <= 1000 for p in res["showing"])


def test_search_accent_and_plural_insensitive():
    a = repo.search_products("violões")["total_found"]
    b = repo.search_products("violao")["total_found"]
    assert a == b > 0


def test_active_promotion_shown_and_pix_not_cumulative():
    p = repo.get_product("127")  # promo ativa (10%)
    assert p["has_active_promotion"] and p["pix_price"] is None
    assert p["discount_percent"] == 10


def test_inactive_promotion_ignored_and_pix_applied():
    p = repo.get_product("96")  # só tem promoções inativas
    assert not p["has_active_promotion"]
    assert p["pix_price"] is not None


def test_product_lookup_by_partial_name():
    p = repo.get_product("Takamine GD20")
    assert p["found"] and "GD20" in p["name"]


def test_unknown_product():
    assert repo.get_product("Fender Telecaster Ouro 24k")["found"] is False


def test_unavailable_product_gets_alternatives():
    with repo._conn() as conn:
        row = conn.execute("SELECT product_id FROM products WHERE status!='active' LIMIT 1").fetchone()
    p = repo.get_product(str(row["product_id"]))
    assert not p["available"] and p["alternatives"]


@pytest.mark.parametrize("price,expected", [(30, 1), (100, 2), (1000, 10), (5000, 12)])
def test_max_installments(price, expected):
    assert repo.max_installments(price) == expected


def test_orders_are_isolated_per_customer():
    res = repo.get_orders(1)
    assert res["found"] and 4 in [o["order_id"] for o in res["orders"]]
    other = repo.get_orders(1, order_id=1)  # pedido 1 é do cliente 3
    assert other["found"] is False


def test_regret_window_depends_on_date(monkeypatch):
    # pedido 4 (cliente 1): entregue, previsão de entrega 2025-12-22
    _set_now(monkeypatch, "2025-12-25T10:00:00")
    inside = repo.get_orders(1, 4)["orders"][0]["policy_check"]
    assert inside["regret_return_7_days"] == "dentro do prazo"
    _set_now(monkeypatch, "2026-11-01T10:00:00")
    outside = repo.get_orders(1, 4)["orders"][0]["policy_check"]
    assert outside["regret_return_7_days"].startswith("FORA")


def test_opening_status(monkeypatch):
    _set_now(monkeypatch, "2026-10-31T14:00:00")  # sábado depois das 13h
    s = repo.opening_status()
    assert not s["is_open_now"] and "segunda-feira" in s["next_opening"]
    _set_now(monkeypatch, "2026-11-02T10:00:00")  # segunda de manhã
    assert repo.opening_status()["is_open_now"]


def test_policy_topics_and_content():
    assert {"payment", "returns_exchanges", "shipping", "opening_hours"} <= set(repo.policy_topics())
    assert "7 dias" in repo.get_policy("returns_exchanges")["content"]
    assert repo.get_policy("nope")["found"] is False
