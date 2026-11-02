"""Loads the store CSVs (data/*.csv) into a SQLite database.

Usage: python -m app.ingest
"""
import csv
import sqlite3
from pathlib import Path

from app.config import DATA_DIR, STORAGE_DIR, STORE_DB

# table -> (csv suffix, [(column, sqlite type)])
SCHEMA = {
    "categories": ("categories.csv", [("category_id", "INTEGER PRIMARY KEY"), ("name", "TEXT"), ("description", "TEXT")]),
    "customers": ("customers.csv", [("customer_id", "INTEGER PRIMARY KEY"), ("name", "TEXT"), ("phone", "TEXT"), ("email", "TEXT"), ("city", "TEXT")]),
    "products": ("products.csv", [("product_id", "INTEGER PRIMARY KEY"), ("price_brl", "REAL"), ("name", "TEXT"), ("category_id", "INTEGER"), ("description", "TEXT"), ("stock_quantity", "INTEGER"), ("status", "TEXT"), ("specs", "TEXT"), ("created_at", "TEXT")]),
    "promotions": ("promotions.csv", [("promotion_id", "INTEGER PRIMARY KEY"), ("product_id", "INTEGER"), ("discount_percent", "REAL"), ("description", "TEXT"), ("is_active", "INTEGER")]),
    "orders": ("orders.csv", [("order_id", "INTEGER PRIMARY KEY"), ("customer_id", "INTEGER"), ("order_date", "TEXT"), ("status", "TEXT"), ("total_brl", "REAL"), ("payment_method", "TEXT"), ("tracking_code", "TEXT"), ("estimated_delivery", "TEXT"), ("notes", "TEXT")]),
    "order_items": ("order_items.csv", [("order_id", "INTEGER"), ("quantity", "INTEGER"), ("product_id", "INTEGER")]),
}


def _find_csv(suffix: str) -> Path:
    # arquivos se chamam "desafio_tecnico_ai_eng - <nome>.csv"
    matches = [p for p in DATA_DIR.glob("*.csv") if p.name.endswith(suffix)]
    if not matches:
        raise FileNotFoundError(f"CSV '*{suffix}' not found in {DATA_DIR}")
    return matches[0]


def _convert(value: str, sql_type: str):
    if value == "":
        return None
    if sql_type.startswith("INTEGER"):
        return int(float(value))
    if sql_type.startswith("REAL"):
        return float(value)
    return value


def build_database(db_path: Path = STORE_DB) -> Path:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    for table, (suffix, columns) in SCHEMA.items():
        conn.execute(f"CREATE TABLE {table} ({', '.join(f'{c} {t}' for c, t in columns)})")
        with open(_find_csv(suffix), encoding="utf-8", newline="") as f:
            rows = [
                [_convert(row[c], t) for c, t in columns] for row in csv.DictReader(f)
            ]
        conn.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(columns))})", rows)
        print(f"{table}: {len(rows)} rows")
    conn.commit()
    conn.close()
    return db_path


if __name__ == "__main__":
    print(f"Database created at {build_database()}")
