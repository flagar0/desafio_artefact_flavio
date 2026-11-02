# Exemplo 12 frete_entrega: Política de frete para Campo Grande e outras cidades

- **Cliente (simulado):** Camila Duarte Nascimento (`customer_id=10`, Campo Grande, `(67) 99567-8901`)
- **Modelo:** `qwen3.5:4b` via Ollama · **Gerado em:** 02/11/2026 11:03 (execução real do agente)
- **Tempo total da conversa:** `54.10s` (1 turno(s))
- As seções `🔧 Rastreamento de Ferramentas (MCP / Tool Calls)` mostram **exatamente como o agente invocou cada função** (argumentos enviados) e **o payload JSON retornado pelo servidor MCP**, servindo como evidência tanto do roteamento do LLM quanto da resposta determinística das ferramentas.

---

### Turno 1

**🧑 Camila:** Como funciona o frete para Campo Grande e para outras cidades?

**🎸 Léo** _(⏱️ `54.10s`)_:

> Para *Campo Grande*, o frete é grátis se seu pedido for acima de R$ 500. Se for menor, a taxa é de R$ 35. A entrega costuma chegar em 1 a 3 dias úteis pelo motoboy.
>
> Para *outras cidades*, temos opções como PAC (5 a 12 dias), SEDEX (2 a 5 dias) ou Jadlog (3 a 8 dias). O valor é calculado automaticamente com base no CEP e peso do instrumento. Se for um item grande, como bateria ou piano, pode precisar de frete especial.
>
> Quer que eu te ajude a ver se algum produto tem esse frete grátis?

**⏱️ Tempo de processamento:** `54.10s` · **Validação do teste:** ✅ PASS (esperado: `get_store_policies`)

#### 🔧 Rastreamento de Ferramentas (MCP / Tool Calls)

**1. Chamada realizada pelo agente:**
```python
get_store_policies(topic='shipping')
```
**Argumentos enviados (JSON):**
```json
{
  "topic": "shipping"
}
```
**Resposta obtida da função (MCP / Tool Output):**
```json
{
  "found": true,
  "topic": "shipping",
  "content": "**Região metropolitana de Campo Grande**\n- Frete grátis para pedidos acima de R$ 500,00; abaixo disso, taxa fixa de R$ 35,00.\n- Prazo: 1 a 3 dias úteis, entrega por motoboy próprio. O cliente é contatado por telefone antes da entrega.\n\n**Outras cidades** (Correios e Jadlog; todos com rastreamento e seguro incluído)\n| Modalidade | Prazo estimado |\n|---|---|\n| PAC (Correios) | 5 a 12 dias úteis |\n| SEDEX (Correios) | 2 a 5 dias úteis |\n| Jadlog (.package) | 3 a 8 dias úteis |\n- O valor do frete é calculado automaticamente com base no CEP, peso e dimensões.\n- Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) podem exigir frete especial com cotação individual.\n- Em caso de avaria, o cliente deve recusar o recebimento e contatar a loja imediatamente.\n\n**Rastreamento**\n- O código é enviado automaticamente por e-mail e WhatsApp quando o pedido é despachado. Formato: BR + 9 caracteres alfanuméricos + BR (ex.: BR4K7M2X9P1BR).\n- Pode ser consultado no site dos Correios ou da Jadlog."
}
```

---
