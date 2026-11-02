"""Data access + deterministic business rules for the store.

All the numeric/date logic (promo price, PIX discount, installments, return windows)
lives here on purpose: a small local LLM should *read* these results, not compute them.
"""
import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta

from app.config import FAKE_NOW, POLICIES_MD, STORE_DB

PIX_DISCOUNT = 0.05
OPENING_HOURS = {  # weekday (Mon=0) -> (open, close) ; Sunday closed
    0: ("09:00", "18:00"), 1: ("09:00", "18:00"), 2: ("09:00", "18:00"),
    3: ("09:00", "18:00"), 4: ("09:00", "18:00"), 5: ("09:00", "13:00"),
}
WEEKDAYS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
ORDER_STATUS_PT = {
    "pending": "pendente (aguardando confirmação de pagamento)",
    "confirmed": "confirmado (em separação)",
    "shipped": "enviado (em trânsito)",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


# ---------------------------------------------------------------- helpers
def now() -> datetime:
    return datetime.fromisoformat(FAKE_NOW) if FAKE_NOW else datetime.now()


def brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _conn() -> sqlite3.Connection:
    if not STORE_DB.exists():
        from app.ingest import build_database

        build_database()
    conn = sqlite3.connect(STORE_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _stem(word: str) -> str:
    """Very small PT-BR stemmer: 'violões'/'violoes' -> 'violao', 'guitarras' -> 'guitarra'."""
    for suffix, repl in (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("s", "")):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)] + repl
    return word


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", _norm(text))]


# ---------------------------------------------------------------- pricing
def max_installments(price: float) -> int:
    """Longest interest-free plan allowed by the policy (min parcel: 3x none*, 4-6x R$80, 7-12x R$100)."""
    best = 1
    for n in range(1, 13):
        parcel = price / n
        minimum = 50 if n <= 3 else 80 if n <= 6 else 100
        if n == 1 or parcel >= minimum:
            best = n
    return best


def _pricing(row: sqlite3.Row, promo: sqlite3.Row | None) -> dict:
    price = row["price_brl"]
    info = {
        "original_price": brl(price),
        "has_active_promotion": promo is not None,
    }
    if promo:
        final = round(price * (1 - promo["discount_percent"] / 100), 2)
        info.update(
            promotion_name=promo["description"],
            discount_percent=promo["discount_percent"],
            final_price=brl(final),
            pix_price=None,
            note="Promoção ativa: o desconto de 5% do PIX NÃO é cumulativo com a promoção.",
        )
    else:
        final = price
        info.update(final_price=brl(price), pix_price=brl(round(price * (1 - PIX_DISCOUNT), 2)))
    n = max_installments(final)
    info["max_installments_no_interest"] = f"{n}x de {brl(final / n)}"
    return info


def _availability(row: sqlite3.Row) -> dict:
    status, stock = row["status"], row["stock_quantity"]
    if status == "discontinued":
        label = "descontinuado (não faz mais parte do catálogo)"
    elif status == "coming_soon":
        label = "em breve (ainda não disponível para compra)"
    elif stock > 0:
        label = "disponível em estoque"
    else:
        label = "esgotado (temporariamente indisponível)"
    return {"available": status == "active" and stock > 0, "availability": label, "stock_quantity": stock}


def _product_view(conn, row: sqlite3.Row, detailed: bool = False) -> dict:
    promo = conn.execute(
        "SELECT * FROM promotions WHERE product_id=? AND is_active=1", (row["product_id"],)
    ).fetchone()
    category = conn.execute("SELECT name FROM categories WHERE category_id=?", (row["category_id"],)).fetchone()
    view = {
        "product_id": row["product_id"],
        "name": row["name"],
        "category": category["name"] if category else None,
        **_availability(row),
        **_pricing(row, promo),
    }
    if detailed:
        view["description"] = row["description"]
        view["specs"] = json.loads(row["specs"]) if row["specs"] else {}
    return view


def _price_now(view: dict) -> float:
    # parse "R$ 1.299,00" back to float for sorting/filtering
    return float(view["final_price"].replace("R$ ", "").replace(".", "").replace(",", "."))


# ---------------------------------------------------------------- catalog
def list_categories() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT c.name, c.description, COUNT(p.product_id) AS products "
            "FROM categories c LEFT JOIN products p ON p.category_id=c.category_id AND p.status='active' "
            "GROUP BY c.category_id"
        ).fetchall()
    return [dict(r) for r in rows]


def search_products(
    query: str = "",
    max_price: float | None = None,
    min_price: float | None = None,
    only_available: bool = True,
    limit: int = 8,
) -> dict:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT p.*, c.name AS category_name FROM products p JOIN categories c USING(category_id)"
        ).fetchall()
        q_tokens = _tokens(query)
        results = []
        for row in rows:
            haystack = set(_tokens(f"{row['name']} {row['category_name']} {row['description']} {row['specs'] or ''}"))
            if not all(t in haystack for t in q_tokens):
                continue
            view = _product_view(conn, row)
            if only_available and not view["available"]:
                continue
            price = _price_now(view)
            if (max_price is not None and price > max_price) or (min_price is not None and price < min_price):
                continue
            results.append(view)
    results.sort(key=_price_now)
    return {"total_found": len(results), "showing": results[:limit], "prices_include": "preço final já com promoção ativa, quando houver"}


def get_product(name_or_id: str) -> dict:
    with _conn() as conn:
        row = None
        if str(name_or_id).strip().isdigit():
            row = conn.execute("SELECT * FROM products WHERE product_id=?", (int(name_or_id),)).fetchone()
        if row is None:
            wanted = set(_tokens(str(name_or_id)))
            best, best_score = None, 0.0
            for r in conn.execute("SELECT * FROM products").fetchall():
                name_tokens = set(_tokens(r["name"]))
                score = len(wanted & name_tokens) / max(len(wanted), 1)
                if score > best_score:
                    best, best_score = r, score
            row = best if best_score >= 0.6 else None
        if row is None:
            return {"found": False, "message": f"Nenhum produto encontrado para '{name_or_id}'."}
        view = _product_view(conn, row, detailed=True)
        view["found"] = True
        if not view["available"]:
            current = _price_now(view)
            alts = conn.execute(
                "SELECT * FROM products WHERE category_id=? AND status='active' AND stock_quantity>0 AND product_id<>?",
                (row["category_id"], row["product_id"]),
            ).fetchall()
            alts = sorted((_product_view(conn, a) for a in alts), key=lambda v: abs(_price_now(v) - current))
            view["alternatives"] = [
                {k: a[k] for k in ("product_id", "name", "final_price", "availability")} for a in alts[:3]
            ]
    return view


# ---------------------------------------------------------------- orders
def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def get_orders(customer_id: int, order_id: int | None = None) -> dict:
    """Orders of ONE customer. customer_id is injected by the application, never by the LLM."""
    today = now().date()
    with _conn() as conn:
        sql, args = "SELECT * FROM orders WHERE customer_id=?", [customer_id]
        if order_id is not None:
            sql, args = sql + " AND order_id=?", args + [order_id]
        orders = conn.execute(sql + " ORDER BY order_date DESC", args).fetchall()
        if not orders:
            return {"found": False, "message": "Nenhum pedido encontrado para este cliente."}
        out = []
        for o in orders:
            items = conn.execute(
                "SELECT p.name, i.quantity FROM order_items i JOIN products p USING(product_id) WHERE i.order_id=?",
                (o["order_id"],),
            ).fetchall()
            order_date, delivery = _parse_date(o["order_date"]), _parse_date(o["estimated_delivery"])
            view = {
                "order_id": o["order_id"],
                "order_date": o["order_date"],
                "status": o["status"],
                "status_pt": ORDER_STATUS_PT.get(o["status"], o["status"]),
                "total": brl(o["total_brl"]),
                "payment_method": o["payment_method"],
                "items": [{"name": i["name"], "quantity": i["quantity"]} for i in items],
                "tracking_code": o["tracking_code"],
                "estimated_delivery": o["estimated_delivery"],
                "notes": o["notes"],
                "days_since_order": (today - order_date).days,
            }
            if o["status"] == "delivered" and delivery:
                # estimated_delivery is the only receipt date we have -> used as proxy
                since = (today - delivery).days
                view["policy_check"] = {
                    "days_since_receipt_approx": since,
                    "regret_return_7_days": "dentro do prazo" if since <= 7 else "FORA do prazo (7 dias corridos após o recebimento)",
                    "defect_exchange_30_days_from_purchase": "dentro do prazo" if (today - order_date).days <= 30 else "fora do prazo",
                    "legal_warranty_90_days": "ativa" if since <= 90 else "expirada",
                    "obs": "Data de recebimento aproximada pela previsão de entrega. Confirmar com a equipe antes de prometer.",
                }
            out.append(view)
    return {"found": True, "today": today.isoformat(), "orders": out}


# ---------------------------------------------------------------- policies / store
def _load_policies() -> dict[str, str]:
    text = POLICIES_MD.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    parts = re.split(r"^## (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def policy_topics() -> list[str]:
    return list(_load_policies())


def get_policy(topic: str) -> dict:
    policies = _load_policies()
    if topic not in policies:
        return {"found": False, "valid_topics": list(policies)}
    return {"found": True, "topic": topic, "content": policies[topic]}


def opening_status() -> dict:
    n = now()
    hours = OPENING_HOURS.get(n.weekday())
    is_open = bool(hours) and hours[0] <= n.strftime("%H:%M") < hours[1]
    # next opening
    probe = n
    while True:
        h = OPENING_HOURS.get(probe.weekday())
        if h:
            opens = probe.replace(hour=int(h[0][:2]), minute=0, second=0, microsecond=0)
            if opens > n:
                break
        probe = (probe + timedelta(days=1)).replace(hour=0, minute=0)
    return {
        "now": n.strftime("%Y-%m-%d %H:%M"),
        "weekday": WEEKDAYS_PT[n.weekday()],
        "is_open_now": is_open,
        "today_hours": f"{hours[0]} às {hours[1]}" if hours else "fechado (domingo)",
        "next_opening": f"{WEEKDAYS_PT[opens.weekday()]}, {opens.strftime('%d/%m')} às {opens.strftime('%H:%M')}",
        "note": "Feriados: loja fechada. Confirmar feriados com a equipe.",
    }


def get_customer(customer_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,)).fetchone()
    return dict(row) if row else None


def list_customers() -> list[dict]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM customers ORDER BY name").fetchall()]
