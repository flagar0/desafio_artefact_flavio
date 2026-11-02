# Exemplo 09 rastreio_pedido: Consulta de pedido em trânsito e código de rastreio

- **Cliente (simulado):** Ana Carolina Ferreira (`customer_id=2`, Campo Grande, `(67) 99654-7821`)
- **Modelo:** `qwen3.5:4b` via Ollama · **Gerado em:** 02/11/2026 11:03 (execução real do agente)
- **Tempo total da conversa:** `65.20s` (1 turno(s))
- As seções `🔧 Rastreamento de Ferramentas (MCP / Tool Calls)` mostram **exatamente como o agente invocou cada função** (argumentos enviados) e **o payload JSON retornado pelo servidor MCP**, servindo como evidência tanto do roteamento do LLM quanto da resposta determinística das ferramentas.

---

### Turno 1

**🧑 Ana:** Oi, qual o status do meu pedido #8 e qual o código de rastreio?

**🎸 Léo** _(⏱️ `65.20s`)_:

> Olá Ana! Seu pedido #8 já foi enviado e está em trânsito. O código de rastreio é *BRJL5544332BR*. A estimativa de entrega era para o dia 28/02/2026. É um violão Kala KA-C Concert Mogno, né?
>
> Precisa de mais alguma informação sobre o envio ou tem outra dúvida? 🎸

**⏱️ Tempo de processamento:** `65.20s` · **Validação do teste:** ✅ PASS (esperado: `get_customer_orders`)

#### 🔧 Rastreamento de Ferramentas (MCP / Tool Calls)

**1. Chamada realizada pelo agente:**
```python
get_customer_orders(customer_id=2, order_id='8')
```
**Argumentos enviados (JSON):**
```json
{
  "customer_id": 2,
  "order_id": "8"
}
```
**Resposta obtida da função (MCP / Tool Output):**
```json
{
  "found": true,
  "today": "2026-11-02",
  "orders": [
    {
      "order_id": 8,
      "order_date": "2026-02-15",
      "status": "shipped",
      "status_pt": "enviado (em trânsito)",
      "total": "R$ 349,90",
      "payment_method": "debit",
      "items": [
        {
          "name": "Kala KA-C Concert Mogno",
          "quantity": 1
        }
      ],
      "tracking_code": "BRJL5544332BR",
      "estimated_delivery": "2026-02-28",
      "notes": null,
      "days_since_order": 260
    }
  ]
}
```

---
