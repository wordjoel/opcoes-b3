"""Núcleo multi-agente do Jarbas.

Os módulos aqui são independentes da interface: o FastAPI injeta o orchestrator,
que coordena especialistas, ferramentas de leitura e memória. Nenhum agente envia
ordens nem escreve dados de mercado; todas as ferramentas são somente leitura.
"""

from app.agents.memory_manager import MemoryManager, MemoryRecord
from app.agents.orchestrator import AgentResult, Orchestrator
from app.agents.specialists import (
    LAB,
    MARKET,
    RISK,
    AgentResponse,
    Specialist,
    specialists_for,
    tool_names_for,
    tools_for,
)
from app.agents.tools import AgentContext, AgentTool, ToolResult, default_tools

__all__ = [
    "AgentContext",
    "AgentResponse",
    "AgentResult",
    "AgentTool",
    "LAB",
    "MARKET",
    "MemoryManager",
    "MemoryRecord",
    "Orchestrator",
    "RISK",
    "Specialist",
    "ToolResult",
    "default_tools",
    "specialists_for",
    "tool_names_for",
    "tools_for",
]
