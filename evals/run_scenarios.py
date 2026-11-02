"""Runs a list of scenarios against the agent and prints/saves results (manual eval / smoke test)."""
import json, sys, time
from app.agent.agent import AgentRuntime, handle_customer_message
from app.storage import chat_store

# (customer_id, [messages])
SCENARIOS = {
    "catalogo": (1, ["Quais opções de violões disponíveis custando até R$1000?"]),
    "endereco": (2, ["Qual o endereço da loja?"]),
    "preco": (3, ["Quanto custa o Takamine GD20?"]),
    "devolucao": (1, ["Me arrependi da minha compra, posso devolver meu pedido?", "Sim, quero devolver."]),
    "fora_escopo": (4, ["Me passa uma receita de bolo de cenoura?"]),
    "acessorio": (5, ["Vocês vendem corda de violão?"]),
}

if __name__ == "__main__":
    names = sys.argv[1:] or list(SCENARIOS)
    rt = AgentRuntime()
    for name in names:
        cid, msgs = SCENARIOS[name]
        chat_store.reset_conversation(cid)
        print(f"\n=== {name} (customer {cid})", flush=True)
        for m in msgs:
            t = time.time()
            r = handle_customer_message(rt, cid, m)
            print(f"[{time.time()-t:.0f}s] Cliente: {m}\nLéo: {r.text}\n  tools={r.tools_used} handoff={r.handoff}", flush=True)
    rt.close()
