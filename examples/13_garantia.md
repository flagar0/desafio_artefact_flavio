# Exemplo 13 garantia: Política de garantia legal e do fabricante

- **Cliente (simulado):** Bruno Carvalho Martins (`customer_id=11`, Três Lagoas, `(67) 98543-2109`)
- **Modelo:** `qwen3.5:4b` via Ollama · **Gerado em:** 02/11/2026 11:03 (execução real do agente)
- **Tempo total da conversa:** `52.91s` (1 turno(s))
- As seções `🔧 Rastreamento de Ferramentas (MCP / Tool Calls)` mostram **exatamente como o agente invocou cada função** (argumentos enviados) e **o payload JSON retornado pelo servidor MCP**, servindo como evidência tanto do roteamento do LLM quanto da resposta determinística das ferramentas.

---

### Turno 1

**🧑 Bruno:** Como funciona a garantia dos instrumentos? Corda arrebentada entra na garantia?

**🎸 Léo** _(⏱️ `52.91s`)_:

> A garantia legal é de 90 dias contra defeitos de fabricação, contados do recebimento. Além disso, a maioria dos instrumentos vem com garantia do fabricante de 6 meses a 2 anos, mas as condições ficam no certificado que acompanha o produto.
>
> Sobre a corda arrebentada: isso geralmente é considerado *desgaste natural*, então não entra na garantia. A garantia cobre defeitos de fabricação (como um problema estrutural ou peça quebrada sem uso), mas não coisas que acontecem com o uso normal, como cordas esticando ou rompendo.
>
> Se você tiver alguma dúvida específica sobre um instrumento ou quiser saber a garantia do fabricante dele, me avise o modelo! 🎸

**⏱️ Tempo de processamento:** `52.91s` · **Validação do teste:** ✅ PASS (esperado: `get_store_policies`)

#### 🔧 Rastreamento de Ferramentas (MCP / Tool Calls)

**1. Chamada realizada pelo agente:**
```python
get_store_policies(topic='warranty')
```
**Argumentos enviados (JSON):**
```json
{
  "topic": "warranty"
}
```
**Resposta obtida da função (MCP / Tool Output):**
```json
{
  "found": true,
  "topic": "warranty",
  "content": "- Garantia legal: 90 dias contra defeitos de fabricação, contados a partir do recebimento pelo cliente (Código de Defesa do Consumidor).\n- Garantia do fabricante: a maioria oferece garantia própria de 6 meses a 2 anos; prazos e condições estão no certificado que acompanha o produto.\n- NÃO cobre: desgaste natural (trastes, cordas, feltros, palhetas de sopro); danos por mau uso, queda ou exposição a condições climáticas extremas; modificações ou reparos por terceiros não autorizados; danos estéticos que não afetem a funcionalidade."
}
```

---
