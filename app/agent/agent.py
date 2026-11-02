"""Customer-service agent: LangChain agent + Ollama (local LLM) + MCP tools.

The MCP server (app/mcp_server/server.py) is spawned as a subprocess and kept alive in a
background event loop, so each customer message does not pay the process start-up cost.
"""
import asyncio
import json
import os
import re
import sys
import threading
import time
from contextlib import AsyncExitStack
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_ollama import ChatOllama

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
class ToolTrace:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    output: Any = None


@dataclass
class AgentReply:
    text: str
    tools_used: list[str] = field(default_factory=list)
    tool_traces: list[ToolTrace] = field(default_factory=list)
    elapsed_seconds: float = 0.0
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


def to_whatsapp(text: str) -> str:
    """Models love Markdown; WhatsApp uses *bold* and plain bullets."""
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    return re.sub(r"^\s*[*-]\s+", "• ", text, flags=re.M)


# Guard rail: the model sometimes *says* it called the team without calling the tool.
# Must NOT match conditional offers ("posso encaminhar...", "se quiser, chamo...").
_PROMISES_HANDOFF = re.compile(
    r"\b(já\s+|vou\s+|estou\s+|acabei\s+de\s+)(avis|encaminh|repass|cham|acion|transfer)\w*[^.!?\n]{0,60}(equipe|atendente|humano|pessoa|gerência)",
    re.I,
)

_STALLS = re.compile(
    r"\b(vou|vamos|posso|preciso|irei|deixa eu)\s+(\w+\s+){0,2}(verificar|consultar|checar|buscar|olhar|ver)\b", re.I
)
_STALL_NUDGE = (
    "[instrução do sistema] Você disse que ia consultar, mas não chamou nenhuma ferramenta. "
    "Chame AGORA a ferramenta adequada, sem pedir permissão ao cliente, e só então responda em português."
)


# Guard rail 3: customer asks about policy/shipping/payment/warranty in a follow-up turn and the small model answers from memory.
_POLICY_INTENTS = [
    ("shipping", re.compile(r"\b(frete|entrega\w*|envio\w*|correios|pac|sedex|jadlog|transportadora|modalidade\w*)\b", re.I)),
    ("payment", re.compile(r"\b(parcela\w*|cart[ãa]o|boleto|d[ée]bito|forma\w*\s+de\s+pagamento)\b", re.I)),
    ("warranty", re.compile(r"\b(garantia)\b", re.I)),
    ("returns_exchanges", re.compile(r"\b(troca\w*|devolu[çc][ãa]o|arrependimento|reembolso)\b", re.I)),
]


def _missing_policy_topic(user_text: str) -> str | None:
    for topic, rx in _POLICY_INTENTS:
        if rx.search(user_text):
            return topic
    return None


def _to_lc(messages: list[dict]):
    out = []
    for m in messages[-HISTORY_LIMIT:]:
        out.append(HumanMessage(m["content"]) if m["sender"] == "customer" else AIMessage(m["content"]))
    return out


def _parse_tool_content(content: Any) -> Any:
    """Convert LangChain/MCP ToolMessage content into a clean Python dict/list/str for inspection."""
    if isinstance(content, list):
        texts = [b.get("text", str(b)) if isinstance(b, dict) else str(b) for b in content]
        content = "\n".join(texts)
    if isinstance(content, str):
        try:
            return json.loads(content)
        except Exception:
            return content
    return content


def _extract_traces(new_messages: list, customer_id: int) -> list[ToolTrace]:
    outputs_by_id = {
        m.tool_call_id: _parse_tool_content(m.content) for m in new_messages if isinstance(m, ToolMessage)
    }
    traces: list[ToolTrace] = []
    for m in new_messages:
        if isinstance(m, AIMessage):
            for tc in m.tool_calls:
                args = dict(tc.get("args") or {})
                if "customer_id" in args:
                    args["customer_id"] = customer_id  # reflect the interceptor override
                traces.append(
                    ToolTrace(
                        name=tc["name"],
                        args=args,
                        output=outputs_by_id.get(tc.get("id")),
                    )
                )
    return traces


class AgentRuntime:
    """Owns a background event loop with the MCP session and the compiled agent."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._agent = None
        self._ready = asyncio.run_coroutine_threadsafe(self._serve(), self._loop)
        self._setup_done = threading.Event()
        if not self._setup_done.wait(timeout=120):
            raise RuntimeError("Agent startup timed out (is Ollama running?)")
        if self._startup_error:
            raise self._startup_error

    def _run(self, coro, timeout: float):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _serve(self) -> None:
        """Single long-lived task: opens the MCP session, waits until close(), then tears it down.
        (anyio requires a cancel scope to be exited by the same task that entered it.)"""
        self._startup_error = None
        self._stop = asyncio.Event()
        try:
            async with AsyncExitStack() as stack:
                await self._setup(stack)
                self._setup_done.set()
                await self._stop.wait()
        except Exception as exc:  # surface startup problems to the caller
            self._startup_error = exc
            self._setup_done.set()

    async def _setup(self, stack: AsyncExitStack) -> None:
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
        session = await stack.enter_async_context(client.session("store"))
        tools = await load_mcp_tools(session, server_name="store", tool_interceptors=[_force_customer_id])
        model = ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.2,
            reasoning=False,  # qwen3.5 "thinking" off: much faster, enough for tool routing
            num_ctx=8192,
        )
        self._agent = create_agent(model, tools + [request_human_handoff])

    async def _run_agent(self, messages: list, customer_id: int) -> tuple[str, list[ToolTrace]]:
        result = await self._agent.ainvoke({"messages": messages}, {"recursion_limit": 14})
        new = result["messages"][len(messages) :]
        traces = _extract_traces(new, customer_id)
        content = new[-1].content if isinstance(new[-1].content, str) else ""
        return to_whatsapp(_strip_thinking(content)), traces

    async def _reply(self, customer: dict, history: list[dict]) -> AgentReply:
        cid = customer["customer_id"]
        _ctx.set({"customer_id": cid})
        messages = [("system", build_system_prompt(customer))] + _to_lc(history)
        text, traces = await self._run_agent(messages, cid)

        # Guard rail 1: small models sometimes announce a lookup ("vou verificar...") without calling a tool,
        # OR answer a policy question (shipping, payment, warranty, returns) from memory in a follow-up turn.
        last_user = next((m["content"] for m in reversed(history) if m["sender"] == "customer"), "")
        missed_topic = _missing_policy_topic(last_user) if not traces else None
        if not traces and (_STALLS.search(text) or missed_topic):
            if missed_topic:
                nudge = (
                    f"[instrução obrigatória] Para responder a pergunta acima, chame IMEDIATAMENTE a ferramenta "
                    f"get_store_policies com topic='{missed_topic}' e responda em português com base no retorno."
                )
                retry = [("system", build_system_prompt(customer)), HumanMessage(f"{last_user}\n\n{nudge}")]
            else:
                retry = messages + [AIMessage(text), HumanMessage(_STALL_NUDGE)]
            text, traces = await self._run_agent(retry, cid)
            if traces:
                traces[0].name = f"{traces[0].name}(retry)"

        tools_used = [t.name for t in traces]

        # Guard rail 2: promised to call the team but did not call the handoff tool.
        handoff = any(t.startswith("request_human_handoff") for t in tools_used)
        if not handoff and _PROMISES_HANDOFF.search(text):
            last = next((m["content"] for m in reversed(history) if m["sender"] == "customer"), "")
            reason = f"[auto] O agente prometeu acionar a equipe. Última mensagem do cliente: {last[:200]}"
            chat_store.request_handoff(cid, reason)
            traces.append(
                ToolTrace(
                    name="request_human_handoff(auto)",
                    args={"reason": reason},
                    output="Equipe notificada automaticamente pelo guard rail.",
                )
            )
            tools_used.append("request_human_handoff(auto)")
            handoff = True
        return AgentReply(text, tools_used, traces, handoff=handoff)

    def reply(self, customer: dict, history: list[dict], timeout: float = 240) -> AgentReply:
        """history = stored messages of this customer, already including the newest customer message."""
        t0 = time.perf_counter()
        try:
            reply = self._run(self._reply(customer, history), timeout)
            reply.elapsed_seconds = round(time.perf_counter() - t0, 2)
            if not reply.text:
                raise RuntimeError("empty model answer")
            return reply
        except Exception as exc:  # guard rail: never leave the customer without an answer
            elapsed = round(time.perf_counter() - t0, 2)
            err = f"Erro técnico no agente: {type(exc).__name__}: {exc}"[:300]
            chat_store.request_handoff(customer["customer_id"], err)
            return AgentReply(
                FALLBACK_REPLY,
                ["error"],
                [ToolTrace(name="error", args={}, output=err)],
                elapsed_seconds=elapsed,
                handoff=True,
            )

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._stop.set)
        try:
            self._ready.result(timeout=15)
        except Exception:
            pass


def handle_customer_message(runtime: AgentRuntime, customer_id: int, text: str) -> AgentReply | None:
    """Full pipeline for one incoming WhatsApp-like message. Returns None if a human owns the thread."""
    chat_store.add_message(customer_id, "customer", text)
    if chat_store.get_conversation(customer_id)["mode"] != chat_store.AGENT:
        return None  # waiting_human / human: agent stays silent
    customer = repo.get_customer(customer_id)
    reply = runtime.reply(customer, chat_store.get_messages(customer_id))
    chat_store.add_message(
        customer_id,
        "agent",
        reply.text,
        reply.tools_used,
        [asdict(t) for t in reply.tool_traces],
        reply.elapsed_seconds,
    )
    return reply
