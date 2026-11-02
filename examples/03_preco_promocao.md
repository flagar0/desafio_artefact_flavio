# Exemplo 03 preco_promocao: Preço de um modelo e promoções ativas

- **Cliente (simulado):** Pedro Henrique Oliveira (id 3)
- **Modelo:** `qwen3.5:4b` via Ollama · **Gerado em:** 01/11/2026 22:42 (execução real do agente)
- As linhas `🔧` mostram as ferramentas (MCP) que o agente chamou antes de responder.

---

**🧑 Pedro:** Quanto custa o Takamine GD20?

**🎸 Léo:**

> O *Takamine GD20* custa *R$ 2.199,00*, mas com pagamento via PIX sai por *R$ 2.089,05*. Ele está disponível em estoque (5 unidades). É um violão dreadnought de cedro sólido, ótimo para fingerstyle.
>
> Precisa de mais alguma informação ou quer ver outras opções? 🎸

🔧 `get_product_details`

---

**🧑 Pedro:** Tem alguma promoção ativa no momento?

**🎸 Léo:**

> Atualmente não há nenhuma promoção ativa no *Takamine GD20*. O preço de *R$ 2.199,00* é o valor final, e o desconto de PIX de *R$ 109,95* já está aplicado como condição de pagamento.
>
> Quer ver outros violões que estão com promoção? 🎸

🔧 `search_products`

---
