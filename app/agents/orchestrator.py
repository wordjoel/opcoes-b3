"""Orquestrador do Jarbas: especialistas → ferramentas → modelo → resposta.

Arquitetura: a coordenação é injetada no FastAPI. O orquestrador não implementa
LLM próprio; ele escolhe áreas, executa apenas as ferramentas permitidas, monta
o prompt com os dados rotulados delega a chamada ao ``ProviderManager``. Assim o
fallback de provedores, os limites e o registro de uso permanecem num só lugar.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.agents.memory_manager import MemoryManager
from app.agents.specialists import Specialist, specialists_for, tool_names_for
from app.agents.tools import AgentContext, AgentTool, ToolResult, default_tools, tools_by_name
from app.jarbas.assistant import StrategyContext, recent_turns, system_prompt
from app.jarbas.providers import Attempt, ChatMessage, ProviderManager
from core.exceptions import DataInsufficientError
from data.providers.base import DataProvider
from db.client import Database
from quant.risk import RiskLimits

Retriever = Callable[[Database, str], str]


@dataclass(frozen=True)
class AgentResult:
    text: str
    provider: str
    model: str
    label: str
    attempts: tuple[Attempt, ...]
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int
    tools: tuple[str, ...]
    tool_details: tuple[ToolResult, ...]
    specialists: tuple[str, ...]
    plan: tuple[str, ...]


class Orchestrator:
    """Coordena um ciclo de pergunta sem guardar estado entre requisições."""

    def __init__(
        self,
        providers: ProviderManager,
        tools: Sequence[AgentTool] | None = None,
        memory: MemoryManager | None = None,
        retriever: Retriever | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.providers = providers
        self.tools = list(tools or default_tools())
        self.memory = memory
        self.retriever = retriever
        self.clock = clock

    def plan_for(self, question: str, context: StrategyContext | None) -> list[Specialist]:
        return specialists_for(question, context is not None)

    def run(
        self,
        *,
        question: str,
        context: StrategyContext | None,
        history: Sequence[ChatMessage],
        db: Database,
        client: httpx.Client,
        provider_factory: Callable[[], DataProvider],
        watchlist: Sequence[str],
        now: datetime,
        provider_order: Sequence[str] | None = None,
        model_chain: str | None = None,
        max_drift: float = RiskLimits().max_spot_drift,
        conversation: str | None = None,
    ) -> AgentResult:
        started = self.clock()
        specialists = self.plan_for(question, context)
        names = tool_names_for(question, context is not None)
        allowed = tools_by_name(names, self.tools)

        memory_text = ""
        if self.memory and conversation and question:
            records = self.memory.recall(db, question)
            memory_text = self.memory.render(records)
        rag_text = ""
        if self.retriever:
            try:
                rag_text = self.retriever(db, question)
            except Exception:  # noqa: BLE001 — RAG é apoio; indisponível não bloqueia a pergunta
                rag_text = ""

        agent_context = AgentContext(
            question=question,
            db=db,
            provider_factory=provider_factory,
            watchlist=watchlist,
            now=now,
            clock=self.clock,
            has_context=context is not None,
            context_symbol=context.symbol if context else None,
            max_drift=max_drift,
            memory_text=memory_text,
            rag_text=rag_text,
        )

        details: list[ToolResult] = []
        blocks: list[str] = []
        for tool in allowed:
            try:
                result = tool.run(agent_context)
            except (DataInsufficientError, ValueError, KeyError, TypeError) as error:
                detail = type(error).__name__
                result = ToolResult(tool.name, f"INDISPONÍVEL ({detail}).", ok=False)
            except Exception:  # noqa: BLE001
                result = ToolResult(tool.name, "INDISPONÍVEL (falha interna na ferramenta).", ok=False)
            details.append(result)
            if result.text:
                blocks.append(result.text)

        data = "\n\n".join(blocks)
        notes = [specialist.note() for specialist in specialists]
        if notes:
            data = "\n".join(notes) + ("\n\n" + data if data else "")
        turns = recent_turns([*history, ChatMessage("user", question)])
        prompt = system_prompt(context, data)

        self.providers.apply(provider_order, model_chain or None)
        completion = self.providers.complete(prompt, turns, client)
        used = tuple(result.name for result in details if result.ok and result.text)
        plan = tuple(
            [f"área:{specialist.name}" for specialist in specialists]
            + [f"ferramenta:{name}" for name in used]
            + ([f"tentativas:{len(completion.attempts)}"] if len(completion.attempts) > 1 else [])
        )
        return AgentResult(
            text=completion.text,
            provider=completion.provider,
            model=completion.model,
            label=completion.label,
            attempts=completion.attempts,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            latency_ms=int((self.clock() - started) * 1000),
            tools=used,
            tool_details=tuple(details),
            specialists=tuple(specialist.name for specialist in specialists),
            plan=plan,
        )
