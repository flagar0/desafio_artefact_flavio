"""Customer-service agent: LangChain agent + Ollama (local LLM) + MCP tools.

The MCP server (app/mcp_server/server.py) is spawned as a subprocess and kept alive in a
background event loop, so each customer message does not pay the process start-up cost.
"""
import asyncio
import re
import sys
import threading
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import dataclass, field

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_ollama import ChatOllama

import os

from app import repository as repo
from app.agent.prompts import build_system_prompt
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, ROOT
from app.storage import chat_store

# Per-request context (which customer is chatting). Set by the runtime, read by tools/interceptors.
_ctx: ContextVar[dict] = ContextVar("agent_ctx")

FALLBACK_REPLY = (
    "Opa, tive um probleminha aqui para processar sua mensagem 😅 "
    "Já avisei alguém da equipe, que vai continuar o atendimento por aqui!"
)
HISTORY_LIMIT = 20  # last N messages sent to the model


@dataclass
class AgentReply:
    text: str
    tools_used: list[str] = field(default_factory=list)
    handoff: bool = False


@tool
async def request_human_handoff(reason: str) -> str:
    """Escalate the conversation to a human attendant (the shopkeeper sees a RED alert and takes over).
    Use when the customer wants to proceed with a cancellation/return/exchange/refund/warranty, complains,
    asks for a person, needs a discount/negotiation/special freight, or when you do not have the information.

    Args:
        reason: short summary in Portuguese of why a human is needed and what the customer wants.
    """
    chat_store.request_handoff(_ctx.get()["customer_id"], reason)
    return "Equipe notificada. Agora avise o cliente, em português, que uma pessoa da equipe vai continuar o atendimento."


async def _force_customer_id(request, handler):
    """Security: the customer_id of order lookups always comes from the app, never from the LLM."""
    if "customer_id" in request.args:
        request = request.override(args={**request.args, "customer_id": _ctx.get()["customer_id"]})
    return await handler(request)


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _to_lc(messages: list[dict]):
    out = []
    for m in messages[-HISTORY_LIMIT:]:
        out.append(HumanMessage(m["content"]) if m["sender"] == "customer" else AIMessage(m["content"]))
    return out


class AgentRuntime:
    """Owns a background event loop with the MCP session and the compiled agent."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._stack = AsyncExitStack()
        self._agent = None
        self._run(self._setup(), timeout=120)

    def _run(self, coro, timeout: float):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _setup(self) -> None:
        client = MultiServerMCPClient(
            {
                "store": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "app.mcp_server.server"],
                    "cwd": str(ROOT),
                    "env": dict(os.environ),
                }
            }
        )
        session = await self._stack.enter_async_context(client.session("store"))
        tools = await load_mcp_tools(session, server_name="store", tool_interceptors=[_force_customer_id])
        model = ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.2,
            reasoning=False,  # qwen3.5 "thinking" off: much faster, enough for tool routing
            num_ctx=8192,
        )
        self._agent = create_agent(model, tools + [request_human_handoff])

    async def _reply(self, customer: dict, history: list[dict]) -> AgentReply:
        _ctx.set({"customer_id": customer["customer_id"]})
        messages = [("system", build_system_prompt(customer))] + _to_lc(history)
        result = await self._agent.ainvoke({"messages": messages}, {"recursion_limit": 14})
        new = result["messages"][len(messages):]
        tools_used = [tc["name"] for m in new if isinstance(m, AIMessage) for tc in m.tool_calls]
        text = _strip_thinking(new[-1].content if isinstance(new[-1].content, str) else "")
        return AgentReply(text, tools_used, handoff="request_human_handoff" in tools_used)

    def reply(self, customer: dict, history: list[dict], timeout: float = 240) -> AgentReply:
        """history = stored messages of this customer, already including the newest customer message."""
        try:
            reply = self._run(self._reply(customer, history), timeout)
            if not reply.text:
                raise RuntimeError("empty model answer")
            return reply
        except Exception as exc:  # guard rail: never leave the customer without an answer
            chat_store.request_handoff(customer["customer_id"], f"Erro técnico no agente: {type(exc).__name__}: {exc}"[:300])
            return AgentReply(FALLBACK_REPLY, ["error"], handoff=True)

    def close(self) -> None:
        self._run(self._stack.aclose(), timeout=15)


def handle_customer_message(runtime: AgentRuntime, customer_id: int, text: str) -> AgentReply | None:
    """Full pipeline for one incoming WhatsApp-like message. Returns None if a human owns the thread."""
    chat_store.add_message(customer_id, "customer", text)
    if chat_store.get_conversation(customer_id)["mode"] != chat_store.AGENT:
        return None  # waiting_human / human: agent stays silent
    customer = repo.get_customer(customer_id)
    reply = runtime.reply(customer, chat_store.get_messages(customer_id))
    chat_store.add_message(customer_id, "agent", reply.text, reply.tools_used)
    return reply
