# Exemplo 08 pix_nao_cumulativo: Promoção ativa vs desconto PIX (regra de não cumulatividade)

- **Cliente (simulado):** Fernanda Ribeiro Souza (`customer_id=8`, Campo Grande, `(67) 99456-7890`)
- **Modelo:** `qwen3.5:4b` via Ollama · **Gerado em:** 02/11/2026 11:03 (execução real do agente)
- **Tempo total da conversa:** `51.03s` (1 turno(s))
- As seções `🔧 Rastreamento de Ferramentas (MCP / Tool Calls)` mostram **exatamente como o agente invocou cada função** (argumentos enviados) e **o payload JSON retornado pelo servidor MCP**, servindo como evidência tanto do roteamento do LLM quanto da resposta determinística das ferramentas.

---

### Turno 1

**🧑 Fernanda:** O violão Crafter HT-100 está em promoção? Se eu pagar no PIX ganho mais 5% de desconto?

**🎸 Léo** _(⏱️ `51.03s`)_:

> Sim, o Crafter HT-100 está em promoção! 🎸
>
> Tem um desconto exclusivo de *18%*, então o preço final é de *R$ 1.967,18* (de R$ 2.399,00).
>
> Sobre o PIX: como a loja já tem uma promoção ativa, o desconto de 5% no PIX *não se soma*. O valor final com PIX seria o mesmo do preço promocional, ou seja, *R$ 1.967,18*.
>
> Quer saber mais detalhes ou ver se há outros modelos?

**⏱️ Tempo de processamento:** `51.03s` · **Validação do teste:** ✅ PASS (esperado: `get_product_details`)

#### 🔧 Rastreamento de Ferramentas (MCP / Tool Calls)

**1. Chamada realizada pelo agente:**
```python
get_product_details(name_or_id='Crafter HT-100')
```
**Argumentos enviados (JSON):**
```json
{
  "name_or_id": "Crafter HT-100"
}
```
**Resposta obtida da função (MCP / Tool Output):**
```json
{
  "product_id": 90,
  "name": "Crafter HT-100 Folk Aço Natural",
  "category": "Violões",
  "available": true,
  "availability": "disponível em estoque",
  "stock_quantity": 3,
  "original_price": "R$ 2.399,00",
  "has_active_promotion": true,
  "promotion_name": "Desconto Exclusivo",
  "discount_percent": 18.0,
  "final_price": "R$ 1.967,18",
  "pix_price": null,
  "note": "Promoção ativa: o desconto de 5% do PIX NÃO é cumulativo com a promoção.",
  "max_installments_no_interest": "12x de R$ 163,93",
  "description": "Violão folk de alta qualidade com tampo sólido em Spruce Engelmann. Projeção sonora superior e acabamento impecável.",
  "specs": {
    "top": "Spruce Engelmann Sólido",
    "back_sides": "Mogno",
    "neck": "Mogno",
    "strings": "steel",
    "scale": "648mm",
    "electronics": "no",
    "color": "Natural"
  },
  "found": true
}
```

---
