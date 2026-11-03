"""Contratos de dados. Todo modelo é imutável e recusa campos desconhecidos.

None significa "não disponível" ou, onde indicado, "ilimitado"; nunca um valor
assumido. Medidas ausentes não têm padrão numérico para não parecerem medidas.
"""

from datetime import date
from enum import Enum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[float, Field(gt=0)]
NonNegative = Annotated[float, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OptionKind(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class LegAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExerciseStyle(str, Enum):
    AMERICAN = "AMERICAN"
    EUROPEAN = "EUROPEAN"


class MarketRegime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOL = "HIGH_VOL"
    UNCERTAIN = "UNCERTAIN"


class SourceKind(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    CACHE = "CACHE"
    # Só para testes: os validadores recusam por padrão.
    TEST = "TEST"


class Provenance(StrictModel):
    """Origem de um dado. Campo obrigatório: dado sem origem não entra no sistema."""

    source: Annotated[str, Field(min_length=1)]
    kind: SourceKind
    collected_at: AwareDatetime
    market_time: AwareDatetime
    delay_seconds: NonNegative | None = None


class MarketSnapshot(StrictModel):
    symbol: str
    price: Positive
    currency: Literal["BRL"] = "BRL"
    volume: Count | None = None
    vwap: Positive | None = None
    regime: MarketRegime | None = None
    provenance: Provenance


class OptionQuote(StrictModel):
    """Cotação como veio da fonte. Inconsistências são apontadas pelos validadores."""

    symbol: str
    underlying: str
    kind: OptionKind
    strike: Positive
    expiry: date
    style: ExerciseStyle | None = None
    bid: NonNegative | None = None
    ask: NonNegative | None = None
    open_interest: Count | None = None
    volume: Count | None = None
    provenance: Provenance


class OptionChain(StrictModel):
    underlying: MarketSnapshot
    quotes: list[OptionQuote]


class PriceBar(StrictModel):
    symbol: str
    day: date
    open: Positive
    high: Positive
    low: Positive
    close: Positive
    volume: Count | None = None
    adjusted: bool
    provenance: Provenance


class OptionLeg(StrictModel):
    symbol: str
    strike: Positive
    expiry: date
    kind: OptionKind
    action: LegAction
    # Quantidade de opções: na B3, um lote padrão de ações equivale a 100.
    quantity: Annotated[int, Field(gt=0)]
    # Preço de execução por opção.
    premium: NonNegative


class StrategyProposal(StrictModel):
    name: str
    legs: Annotated[list[OptionLeg], Field(min_length=1)]
    # Em R$. None = ilimitado.
    max_profit: float | None
    # Em R$, como valor positivo. None = ilimitada.
    max_loss: NonNegative | None
    breakeven_points: list[float]
    # None quando ganho ou perda não têm limite ou a perda é zero.
    risk_reward_ratio: NonNegative | None
    rationale: str
    assumptions: list[str]


class RiskAssessment(StrictModel):
    is_approved: bool
    # None = liquidez não medida, o que é diferente de liquidez zero.
    liquidity_score: Annotated[float, Field(ge=0, le=1)] | None
    stress_test_results: dict[str, float]
    warnings: list[str]
    final_verdict: str
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def _rejection_needs_reason(self) -> "RiskAssessment":
        if not self.is_approved and not self.rejection_reason:
            raise ValueError("Reprovação exige rejection_reason")
        if self.is_approved and self.liquidity_score is None:
            raise ValueError("Não há aprovação sem medir a liquidez")
        return self
