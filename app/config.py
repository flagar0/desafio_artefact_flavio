"""Central configuration (paths + model settings)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
STORAGE_DIR = ROOT / "storage_data"
STORE_DB = STORAGE_DIR / "store.db"  # catalogo/pedidos/clientes (gerado a partir dos CSVs)
CHAT_DB = STORAGE_DIR / "chat.db"  # historico das conversas (runtime)
POLICIES_MD = ROOT / "app" / "knowledge" / "politicas.md"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# "Hoje" do sistema. Os dados da loja vao ate 2026-03; por padrao usamos a data real da maquina.
# Pode ser fixada via env para demos reprodutiveis (ex.: FAKE_NOW=2026-03-20T10:00:00).
FAKE_NOW = os.getenv("FAKE_NOW")
