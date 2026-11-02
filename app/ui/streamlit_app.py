"""Streamlit prototype: WhatsApp-like simulator (customer view) + shopkeeper dashboard.

Run:  streamlit run app/ui/streamlit_app.py

PROTOTYPE: one Streamlit process, SQLite persistence, manual refresh for the shopkeeper view.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app import repository as repo
from app.agent.agent import AgentRuntime, handle_customer_message
from app.config import OLLAMA_MODEL
from app.storage import chat_store as store

st.set_page_config(page_title="Empório da Música - Atendimento", page_icon="🎸", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] .stButton button {text-align:left; justify-content:flex-start; width:100%;}
    .proto-badge {background:#25D366; color:white; padding:2px 10px; border-radius:10px; font-size:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Iniciando agente (MCP + Ollama)...")
def get_runtime() -> AgentRuntime:
    return AgentRuntime()


runtime = get_runtime()
customers = {c["customer_id"]: c for c in repo.list_customers()}
conversations = store.list_conversations()

if "customer_id" not in st.session_state:
    st.session_state.customer_id = next(iter(customers))

# ------------------------------------------------------------------ sidebar: contacts
with st.sidebar:
    st.markdown("### 🎸 Empório da Música")
    st.markdown('<span class="proto-badge">PROTÓTIPO</span>', unsafe_allow_html=True)
    st.caption(f"Modelo local: `{OLLAMA_MODEL}`")
    view = st.radio("Visão", ["📱 Cliente (WhatsApp)", "🏪 Lojista"], horizontal=False)
    is_shop = view.startswith("🏪")
    st.divider()

    st.markdown("**Conversas**")
    mode_icon = {store.WAITING_HUMAN: "🔴", store.HUMAN: "🟡", store.AGENT: "🟢"}
    # alerts first, then most recent
    by_recent = sorted(conversations.values(), key=lambda c: c["updated_at"] or "", reverse=True)
    ordered = [c for c in by_recent if c["mode"] == store.WAITING_HUMAN] + [
        c for c in by_recent if c["mode"] != store.WAITING_HUMAN
    ]
    for c in ordered:
        name = customers[c["customer_id"]]["name"]
        label = f"{mode_icon[c['mode']]} {name}"
        if st.button(label, key=f"conv_{c['customer_id']}", help=(c["last_message"] or "")[:120]):
            st.session_state.customer_id = c["customer_id"]
            st.rerun()
    if not ordered:
        st.caption("Nenhuma conversa ainda.")

    st.divider()
    chosen = st.selectbox(
        "Abrir/iniciar conversa com cliente",
        options=list(customers),
        format_func=lambda i: f"{customers[i]['name']} · {customers[i]['phone']}",
        index=list(customers).index(st.session_state.customer_id),
    )
    if chosen != st.session_state.customer_id:
        st.session_state.customer_id = chosen
        st.rerun()
    st.button("🔄 Atualizar", on_click=st.rerun)

cid = st.session_state.customer_id
customer = customers[cid]
conv = store.get_conversation(cid)

# ------------------------------------------------------------------ global red alert (shopkeeper)
waiting = [c for c in conversations.values() if c["mode"] == store.WAITING_HUMAN]
if is_shop and waiting:
    for c in waiting:
        cu = customers[c["customer_id"]]
        st.error(
            f"🔴 **ATENÇÃO - {cu['name']}** ({cu['phone']}) precisa de atendimento humano.\n\n"
            f"**Motivo:** {c['handoff_reason']}  \n_Pedido do agente em {c['handoff_at']}_"
        )

# ------------------------------------------------------------------ chat header
st.subheader(f"{customer['name']}  ·  {customer['phone']}")
st.caption(f"Cliente #{cid} · {customer['email']} · {customer['city']}")

if is_shop:
    if conv["mode"] == store.WAITING_HUMAN:
        st.warning("O agente pediu ajuda e **parou de responder** nesta conversa.")
        if st.button("✋ Assumir conversa", type="primary"):
            store.set_mode(cid, store.HUMAN)
            st.rerun()
    elif conv["mode"] == store.HUMAN:
        st.info("🟡 Você está no controle. O agente não responde enquanto você não devolver.")
        if st.button("🤖 Devolver ao agente"):
            store.set_mode(cid, store.AGENT)
            st.rerun()
    else:
        st.success("🟢 O agente está atendendo sozinho.")
        if st.button("✋ Assumir mesmo assim"):
            store.set_mode(cid, store.HUMAN)
            st.rerun()
    if st.button("🗑️ Limpar conversa (demo)"):
        store.reset_conversation(cid)
        st.rerun()

# ------------------------------------------------------------------ transcript
AVATARS = {"customer": "🧑", "agent": "🎸", "human": "🧑‍💼"}
ROLE = {"customer": "user", "agent": "assistant", "human": "assistant"}


def whatsapp_to_markdown(text: str) -> str:
    """WhatsApp *bold* -> Markdown **bold** so the preview looks like the real app."""
    return re.sub(r"(?<![\*\w])\*([^*\n]+)\*(?![\*\w])", r"**\1**", text)


def render(msg: dict) -> None:
    with st.chat_message(ROLE[msg["sender"]], avatar=AVATARS[msg["sender"]]):
        if msg["sender"] == "human":
            st.caption("Atendente (loja)")
        st.markdown(whatsapp_to_markdown(msg["content"]))
        if is_shop and msg["sender"] == "agent":
            elapsed = f" · ⏱️ {msg['elapsed_seconds']:.2f}s" if msg.get("elapsed_seconds") else ""
            tools = msg["tools_used"].strip("[]").replace(chr(34), "") if msg.get("tools_used") else "nenhuma"
            st.caption(f"🔧 ferramentas: {tools}{elapsed}")
            if msg.get("tool_traces"):
                for tr in json.loads(msg["tool_traces"]):
                    with st.expander(f"🔎 `{tr['name']}({json.dumps(tr.get('args') or {}, ensure_ascii=False)})`"):
                        st.json(tr.get("output"))
        st.caption(msg["created_at"][11:16])


messages = store.get_messages(cid)
if not messages:
    st.caption("Nenhuma mensagem ainda. Diga um oi 👋")
for m in messages:
    render(m)

# ------------------------------------------------------------------ input
if is_shop:
    if conv["mode"] == store.HUMAN:
        text = st.chat_input("Responder como atendente da loja...")
        if text:
            store.add_message(cid, "human", text)
            st.rerun()
    else:
        st.chat_input("Assuma a conversa para responder como atendente", disabled=True)
else:
    text = st.chat_input(f"Mensagem como {customer['name'].split()[0]}...")
    if text:
        with st.chat_message("user", avatar=AVATARS["customer"]):
            st.markdown(text)
        with st.spinner("Léo está digitando..."):
            handle_customer_message(runtime, cid, text)
        st.rerun()
    if conv["mode"] != store.AGENT:
        st.caption("⏳ Sua mensagem foi encaminhada à equipe da loja, que continuará o atendimento por aqui.")
