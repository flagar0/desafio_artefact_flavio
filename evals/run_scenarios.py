"""Mini evaluation + example exporter.

  python -m evals.run_scenarios                # run all scenarios, check expected tools
  python -m evals.run_scenarios 03_preco       # run a subset
  python -m evals.run_scenarios --export       # also write examples/<scenario>.md
"""
import sys
import time
from datetime import datetime

from app import repository as repo
from app.agent.agent import AgentRuntime, handle_customer_message
from app.config import OLLAMA_MODEL, ROOT
from app.storage import chat_store

# name -> (title, customer_id, [(message, expected tool or None)])
SCENARIOS = {
    "01_catalogo": ("Consulta ao catálogo com orçamento", 1, [
        ("Quais opções de violões disponíveis custando até R$1000?", "search_products"),
        ("Me fala mais do Yamaha C40", "get_product_details"),
    ]),
    "02_loja": ("Informações gerais da loja (endereço e horário)", 2, [
        ("Qual o endereço da loja?", "get_store_policies"),
        ("E vocês estão abertos agora?", "get_opening_status"),
    ]),
    "03_preco_promocao": ("Preço de um modelo e promoções ativas", 3, [
        ("Quanto custa o Takamine GD20?", "get_product_details"),
        ("Tem alguma promoção ativa no momento?", "search_products"),
    ]),
    "04_devolucao": ("Arrependimento de compra: política + dados do pedido + handoff humano", 1, [
        ("Me arrependi da minha compra, posso devolver meu pedido?", "get_customer_orders"),
        ("Sim, quero devolver.", "request_human_handoff"),
    ]),
    "05_fora_escopo": ("Fora de escopo e acessórios", 4, [
        ("Me passa uma receita de bolo de cenoura?", None),
        ("Vocês vendem corda de violão?", None),
    ]),
    "06_produto_esgotado": ("Produto esgotado e sugestão de alternativas", 6, [
        ("Vocês têm o violão Giannini GF-3D em estoque?", "get_product_details"),
    ]),
    "07_produto_descontinuado": ("Produto descontinuado e alternativas", 7, [
        ("Quero comprar o violão 7 cordas Shelby SN-7C, quanto está?", "get_product_details"),
    ]),
    "08_pix_nao_cumulativo": ("Promoção ativa vs desconto PIX (regra de não cumulatividade)", 8, [
        ("O violão Crafter HT-100 está em promoção? Se eu pagar no PIX ganho mais 5% de desconto?", "get_product_details"),
    ]),
    "09_rastreio_pedido": ("Consulta de pedido em trânsito e código de rastreio", 2, [
        ("Oi, qual o status do meu pedido #8 e qual o código de rastreio?", "get_customer_orders"),
    ]),
    "10_pedido_cancelado": ("Consulta de motivo de pedido cancelado", 17, [
        ("Por que o meu pedido foi cancelado?", "get_customer_orders"),
    ]),
    "11_formas_pagamento": ("Regras de pagamento e parcelamento", 9, [
        ("Quais são as formas de pagamento e as regras de parcelamento no cartão?", "get_store_policies"),
    ]),
    "12_frete_entrega": ("Política de frete para Campo Grande e outras cidades", 10, [
        ("Como funciona o frete para Campo Grande e para outras cidades?", "get_store_policies"),
    ]),
    "13_garantia": ("Política de garantia legal e do fabricante", 11, [
        ("Como funciona a garantia dos instrumentos? Corda arrebentada entra na garantia?", "get_store_policies"),
    ]),
    "14_categorias": ("Listagem de categorias do catálogo", 12, [
        ("Quais categorias de instrumentos vocês vendem na loja?", "list_categories"),
    ]),
    "15_reclamacao_handoff": ("Reclamação de defeito e escalonamento humano", 5, [
        ("Meu instrumento chegou com o braço empenado, quero abrir uma reclamação e falar com um atendente agora!", "request_human_handoff"),
    ]),
}


def export_md(name, title, cid, turns) -> None:
    customer = repo.get_customer(cid)
    lines = [
        f"# Exemplo {name.replace('_', ' ', 1)}: {title}",
        "",
        f"- **Cliente (simulado):** {customer['name']} (id {cid})",
        f"- **Modelo:** `{OLLAMA_MODEL}` via Ollama · **Gerado em:** {datetime.now():%d/%m/%Y %H:%M} (execução real do agente)",
        "- As linhas `🔧` mostram as ferramentas (MCP) que o agente chamou antes de responder.",
        "",
        "---",
        "",
    ]
    for msg, reply in turns:
        lines += [f"**🧑 {customer['name'].split()[0]}:** {msg}", ""]
        lines += [f"**🎸 Léo:**", ""] + [f"> {l}" if l else ">" for l in reply.text.splitlines()] + [""]
        tools = ", ".join(f"`{t}`" for t in reply.tools_used) or "nenhuma (resposta direta)"
        lines += [f"🔧 {tools}", ""]
        if reply.handoff:
            lines += ["🔴 **Alerta no painel do lojista:** conversa marcada como _aguardando humano_; o agente para de responder até o lojista assumir.", ""]
        lines += ["---", ""]
    out = ROOT / "examples"
    out.mkdir(exist_ok=True)
    (out / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    export = "--export" in sys.argv
    names = [n for n in SCENARIOS if not args or any(n.startswith(a) for a in args)]
    rt = AgentRuntime()
    failures = 0
    for name in names:
        title, cid, turns = SCENARIOS[name]
        chat_store.reset_conversation(cid)
        print(f"\n=== {name}: {title} (customer {cid})", flush=True)
        done = []
        for msg, expected in turns:
            t = time.time()
            r = handle_customer_message(rt, cid, msg)
            ok = expected is None or any(expected in u for u in r.tools_used)
            failures += not ok
            print(f"[{time.time()-t:.0f}s] {'PASS' if ok else 'FAIL'} (esperado: {expected}) tools={r.tools_used}\n  Cliente: {msg}\n  Léo: {r.text}", flush=True)
            done.append((msg, r))
        if export:
            export_md(name, title, cid, done)
    rt.close()
    print(f"\n{'OK' if not failures else str(failures) + ' FAILURE(S)'}")
    sys.exit(1 if failures else 0)
