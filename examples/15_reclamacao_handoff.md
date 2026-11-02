# Exemplo 15 reclamacao_handoff: Reclamação de defeito e escalonamento humano

- **Cliente (simulado):** Rafael Augusto Pereira (id 5)
- **Modelo:** `qwen3.5:4b` via Ollama · **Gerado em:** 01/11/2026 23:03 (execução real do agente)
- As linhas `🔧` mostram as ferramentas (MCP) que o agente chamou antes de responder.

---

**🧑 Rafael:** Meu instrumento chegou com o braço empenado, quero abrir uma reclamação e falar com um atendente agora!

**🎸 Léo:**

> Olá Rafael! Que pena que seu instrumento veio com o braço empenado, isso pode afetar muito o som. Como você quer falar com um atendente sobre essa situação específica, vou encaminhar seu caso para a equipe agora mesmo.
>
> Vou avisar a equipe sobre a reclamação do produto com defeito e eles vão continuar a conversa por aqui. Em breve alguém vai responder! 🎸

🔧 `request_human_handoff(auto)`

🔴 **Alerta no painel do lojista:** conversa marcada como _aguardando humano_; o agente para de responder até o lojista assumir.

---
