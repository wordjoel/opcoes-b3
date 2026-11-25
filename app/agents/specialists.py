"""Especialistas determinísticos do Jarbas.

Arquitetura: um especialista não chama um modelo próprio. Ele apenas (1) reconhece
se a pergunta é da sua área, (2) limita as ferramentas que pode usar e (3) acrescenta
uma nota curta ao prompt. O modelo continua sendo o único gerador de texto, e as
regras de procedência e decisão do app continuam intactas.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.jarbas.tools import intents_of


@dataclass(frozen=True)
class Specialist:
    name: str
    description: str
    tool_names: tuple[str, ...]
    pattern: re.Pattern[str]

    def applies(self, question: str, has_context: bool) -> bool:
        return bool(self.pattern.search(question))

    def note(self) -> str:
        return f"ÁREA {self.name}: {self.description}"


@dataclass(frozen=True)
class AgentResponse:
    text: str
    specialist: str
    tool_names: tuple[str, ...]


MARKET = Specialist(
    "scanner",
    "Dados de mercado vêm do Scanner, com rótulo REAL/HISTÓRICO/CALCULADO. Cite a grade e avise se ela estiver defasada.",
    ("mercado", "rag", "memoria"),
    re.compile(r"mercado|scanner|oportunidad|sinal|sinais|volatil|hoje|aten[çc][ãa]o|regime|ativo|\biv\b", re.I),
)

LAB = Specialist(
    "lab",
    "O Laboratório calcula payoff e ranking com prêmios de fechamento: resultados são hipotéticos, não operação executada.",
    ("travas", "rag", "memoria"),
    re.compile(r"trava|spread|payoff|lab|laborat[óo]rio|simula|backtest|rent[áa]ve|risco.?retorno", re.I),
)

RISK = Specialist(
    "risco",
    "A decisão APROVADA/REPROVADA/INCOMPLETA é das regras fixas e do RiskManager com a carteira real; nunca a substitua.",
    ("hedge_risco", "carteira", "decisoes", "rag", "memoria"),
    re.compile(r"hedge|prote[çc][ãa]o|proteger|cobertura|risco|carteira|posi[çc][ãa]o|decis|aprovad|reprovad", re.I),
)

ALL = (MARKET, LAB, RISK)


def specialists_for(question: str, has_context: bool, watchlist: Sequence[str] = ()) -> list[Specialist]:
    """Escolhe areas em ordem estável. Pergunta conceitual com estrutura não ativa nada."""
    found = [specialist for specialist in ALL if specialist.applies(question, has_context)]
    if not found and not has_context:
        # Panorama de mercado é a área padrão quando não há estrutura na tela.
        found = [MARKET]
    if "mercado" in intents_of(question, has_context) and MARKET not in found:
        found.insert(0, MARKET)
    return found


def tools_for(specialists: Sequence[Specialist]) -> list[str]:
    """União das ferramentas das áreas escolhidas, sem duplicatas."""
    names: list[str] = []
    for specialist in specialists:
        for name in specialist.tool_names:
            if name not in names:
                names.append(name)
    return names


_INTENT_TO_TOOL = {"mercado": "mercado", "travas": "travas", "carteira": "carteira", "decisoes": "decisoes"}
_HEDGE = re.compile(r"\bhedge\b|prote[çc][ãa]o|proteger|cobertura", re.I)


def tool_names_for(question: str, has_context: bool) -> list[str]:
    """Nomes das ferramentas que o orquestrador pode executar nesta pergunta.

    As intenções fixas do Jarbas continuam comandando a leitura de mercado, carteira,
    travas e decisões; os especialistas só acrescentam a ferramenta de hedge e os
    contextos de RAG/memória. Assim o contrato observado pelo frontend não muda.
    """
    names: list[str] = []
    for intent in intents_of(question, has_context):
        name = _INTENT_TO_TOOL.get(intent)
        if name and name not in names:
            names.append(name)
    if _HEDGE.search(question) and "hedge_risco" not in names:
        names.insert(0, "hedge_risco")
    for name in ("rag", "memoria"):
        if name not in names:
            names.append(name)
    return names
