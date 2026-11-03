"""Monta as estruturas de um único vencimento a partir de cotações já validadas.

Regras determinísticas, sem IA: cada perna busca o strike mais próximo de um alvo
definido pelo preço do ativo. Se a grade não tiver esse strike, a estrutura é listada
como indisponível, em vez de ser montada com outra forma. Calendário e diagonal ficam
de fora porque o payoff no vencimento não os define.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from core.types import LegAction, MarketRegime, OptionKind, OptionLeg, OptionQuote, StrategyProposal
from quant.payoff import analyze_payoff

BUY, SELL = LegAction.BUY, LegAction.SELL
CALL, PUT = OptionKind.CALL, OptionKind.PUT

# Distância entre os strikes das pernas, como fração do ativo.
DEFAULT_WIDTH = 0.05
# Um lote padrão na B3.
DEFAULT_LOT = 100
# A partir destas razões entre volatilidade implícita e histórica, a opção está cara ou barata.
RICH_IV_RATIO = 1.3
CHEAP_IV_RATIO = 0.8


class PriceBasis(str, Enum):
    # Compra no ask e venda no bid.
    BOOK = "BOOK"
    # Último preço do pregão: indicativo, sem garantia de execução.
    CLOSE = "CLOSE"


@dataclass(frozen=True)
class _LegSpec:
    action: LegAction
    kind: OptionKind
    # Em larguras acima (+) ou abaixo (-) do ativo; 0 é o strike mais próximo dele.
    offset: int
    ratio: int = 1


@dataclass(frozen=True)
class _Structure:
    key: str
    name: str
    legs: tuple[_LegSpec, ...]
    rationale: str
    # Regimes em que a estrutura faz sentido.
    regimes: frozenset[MarketRegime] = frozenset()
    # Comprada em volatilidade: compatível quando a implícita está barata.
    long_vol: bool = False
    # As pernas em offset 0 precisam dividir o strike.
    shared_center: bool = False


_BULL, _BEAR = MarketRegime.BULL, MarketRegime.BEAR
_SIDE, _HIGH = MarketRegime.SIDEWAYS, MarketRegime.HIGH_VOL

STRUCTURES: tuple[_Structure, ...] = (
    _Structure(
        "long_call", "Compra de call", (_LegSpec(BUY, CALL, 0),),
        "Ganha com alta forte; a perda se limita ao prêmio pago.", frozenset({_BULL}),
    ),
    _Structure(
        "long_put", "Compra de put", (_LegSpec(BUY, PUT, 0),),
        "Ganha com queda forte; a perda se limita ao prêmio pago.", frozenset({_BEAR}),
    ),
    _Structure(
        "bull_call_spread", "Trava de alta com call", (_LegSpec(BUY, CALL, 0), _LegSpec(SELL, CALL, 1)),
        "Alta moderada, com débito menor que o da call sozinha e ganho limitado.", frozenset({_BULL}),
    ),
    _Structure(
        "bear_put_spread", "Trava de baixa com put", (_LegSpec(BUY, PUT, 0), _LegSpec(SELL, PUT, -1)),
        "Queda moderada, com débito menor que o da put sozinha e ganho limitado.", frozenset({_BEAR}),
    ),
    _Structure(
        "bull_put_spread", "Trava de alta com put", (_LegSpec(SELL, PUT, -1), _LegSpec(BUY, PUT, -2)),
        "Recebe crédito se o ativo ficar acima da put vendida.", frozenset({_BULL, _HIGH}),
    ),
    _Structure(
        "bear_call_spread", "Trava de baixa com call", (_LegSpec(SELL, CALL, 1), _LegSpec(BUY, CALL, 2)),
        "Recebe crédito se o ativo ficar abaixo da call vendida.", frozenset({_BEAR, _HIGH}),
    ),
    _Structure(
        "long_straddle", "Straddle comprado", (_LegSpec(BUY, CALL, 0), _LegSpec(BUY, PUT, 0)),
        "Ganha com movimento grande em qualquer direção; precisa de volatilidade barata.",
        long_vol=True, shared_center=True,
    ),
    _Structure(
        "long_strangle", "Strangle comprado", (_LegSpec(BUY, CALL, 1), _LegSpec(BUY, PUT, -1)),
        "Como o straddle, mais barato, mas exige um movimento maior.", long_vol=True,
    ),
    _Structure(
        "iron_condor", "Iron condor",
        (_LegSpec(BUY, PUT, -2), _LegSpec(SELL, PUT, -1), _LegSpec(SELL, CALL, 1), _LegSpec(BUY, CALL, 2)),
        "Recebe crédito se o ativo ficar dentro da faixa; favorece volatilidade cara.", frozenset({_SIDE, _HIGH}),
    ),
    _Structure(
        "iron_butterfly", "Iron butterfly",
        (_LegSpec(BUY, PUT, -1), _LegSpec(SELL, PUT, 0), _LegSpec(SELL, CALL, 0), _LegSpec(BUY, CALL, 1)),
        "Crédito maior que o do condor, com faixa de lucro mais estreita.", frozenset({_SIDE, _HIGH}),
        shared_center=True,
    ),
    _Structure(
        "call_butterfly", "Borboleta com call",
        (_LegSpec(BUY, CALL, -1), _LegSpec(SELL, CALL, 0, 2), _LegSpec(BUY, CALL, 1)),
        "Débito pequeno, com ganho máximo se o ativo terminar no strike central.", frozenset({_SIDE}),
    ),
)
_BY_KEY = {structure.key: structure for structure in STRUCTURES}

# Delta absoluto alvo de cada perna, na ordem de `legs`. Pontos de partida do projeto, não
# garantia de melhor relação de risco. As demais estruturas continuam centradas no ativo.
_CONDOR = lambda wing, body: (wing, body, body, wing)  # noqa: E731
PROFILES: dict[str, dict[str, tuple[float, ...]]] = {
    "CONSERVATIVE": {
        "bull_call_spread": (0.40, 0.20),
        "bear_put_spread": (0.40, 0.20),
        "bull_put_spread": (0.20, 0.10),
        "bear_call_spread": (0.20, 0.10),
        "long_strangle": (0.20, 0.20),
        "iron_condor": _CONDOR(0.10, 0.20),
    },
    "MODERATE": {
        "bull_call_spread": (0.45, 0.25),
        "bear_put_spread": (0.45, 0.25),
        "bull_put_spread": (0.25, 0.12),
        "bear_call_spread": (0.25, 0.12),
        "long_strangle": (0.25, 0.25),
        "iron_condor": _CONDOR(0.15, 0.25),
    },
    "AGGRESSIVE": {
        "bull_call_spread": (0.50, 0.30),
        "bear_put_spread": (0.50, 0.30),
        "bull_put_spread": (0.35, 0.15),
        "bear_call_spread": (0.35, 0.15),
        "long_strangle": (0.30, 0.30),
        "iron_condor": _CONDOR(0.20, 0.30),
    },
}
# Em opções: 50 e 100 contratos de 100 opções.
MIN_DELTA_VOLUME = 5_000
MIN_DELTA_OPEN_INTEREST = 10_000
# Mais longe que isto do alvo, a perna já não corresponde ao perfil.
_DELTA_TOLERANCE = 0.10


@dataclass(frozen=True)
class Candidate:
    key: str
    proposal: StrategyProposal
    quotes: tuple[OptionQuote, ...]
    bases: tuple[PriceBasis, ...]


@dataclass(frozen=True)
class Unavailable:
    key: str
    name: str
    reason: str


def execution_price(quote: OptionQuote, action: LegAction, use_book: bool = True) -> tuple[float, PriceBasis]:
    """Lado desfavorável do livro, quando ele é válido e existe; senão, o fechamento."""
    if use_book and quote.bid and quote.ask:
        return (quote.ask if action is BUY else quote.bid), PriceBasis.BOOK
    if quote.close:
        return quote.close, PriceBasis.CLOSE
    raise ValueError(f"{quote.symbol}: sem preço")


def _nearest(quotes: Sequence[OptionQuote], kind: OptionKind, target: float) -> OptionQuote | None:
    of_kind = [quote for quote in quotes if quote.kind is kind]
    return min(of_kind, key=lambda quote: (abs(quote.strike - target), quote.strike), default=None)


def _pick_by_delta(
    structure: _Structure, targets: tuple[float, ...], quotes: Sequence[OptionQuote]
) -> tuple[list[OptionQuote], str | None]:
    pool = [
        quote
        for quote in quotes
        if quote.delta is not None
        and (quote.volume or 0) >= MIN_DELTA_VOLUME
        and (quote.open_interest or 0) >= MIN_DELTA_OPEN_INTEREST
    ]
    picked: list[OptionQuote] = []
    for spec, target in zip(structure.legs, targets):
        of_kind = [quote for quote in pool if quote.kind is spec.kind]
        if not of_kind:
            return [], f"sem {spec.kind.value} líquida com delta informado"
        best = min(of_kind, key=lambda quote: (abs(abs(quote.delta) - target), quote.strike))
        if abs(abs(best.delta) - target) > _DELTA_TOLERANCE:
            return [], f"sem {spec.kind.value} líquida perto do delta alvo {target:.2f}"
        picked.append(best)
    return picked, None


def _pick_quotes(
    structure: _Structure,
    quotes: Sequence[OptionQuote],
    spot: float,
    width: float,
    targets: tuple[float, ...] | None = None,
) -> tuple[list[OptionQuote], str | None]:
    if targets:
        picked, reason = _pick_by_delta(structure, targets, quotes)
        if reason:
            return [], reason
    else:
        picked = []
        for spec in structure.legs:
            target = spot * (1 + spec.offset * width)
            quote = _nearest(quotes, spec.kind, target)
            # Mais longe que meia largura, a perna já teria outra função na estrutura.
            if quote is None or abs(quote.strike - target) > spot * width / 2:
                return [], f"sem {spec.kind.value} negociada perto de {target:.2f}"
            picked.append(quote)

    if structure.shared_center:
        centers = {q.strike for q, spec in zip(picked, structure.legs) if spec.offset == 0}
        if len(centers) > 1:
            return [], "call e put centrais em strikes diferentes"
    by_kind: dict[OptionKind, dict[int, float]] = {}
    for quote, spec in zip(picked, structure.legs):
        by_kind.setdefault(spec.kind, {})[spec.offset] = quote.strike
    for strikes in by_kind.values():
        ordered = [strikes[offset] for offset in sorted(strikes)]
        if any(low >= high for low, high in zip(ordered, ordered[1:])):
            return [], "a grade não tem strikes distintos para as pernas"
    return picked, None


def build_candidates(
    quotes: Sequence[OptionQuote],
    spot: float,
    lot: int = DEFAULT_LOT,
    width: float = DEFAULT_WIDTH,
    use_book: bool = True,
    profile: str | None = None,
) -> tuple[list[Candidate], list[Unavailable]]:
    """`quotes` devem ser as utilizáveis do relatório de validação, de um só vencimento.

    `use_book=False` em grade de fim de dia, cujo livro é só sobra de ofertas.
    Com `profile`, as estruturas de PROFILES escolhem strikes por delta entre as séries líquidas.
    """
    if profile is not None and profile not in PROFILES:
        raise ValueError(f"Perfil desconhecido: {profile}")
    targets_by_key = PROFILES[profile] if profile else {}
    if spot <= 0 or lot <= 0 or not 0 < width < 0.5:
        raise ValueError("Parâmetros de montagem inválidos")
    if len({quote.expiry for quote in quotes}) > 1:
        raise ValueError("As cotações precisam ser de um único vencimento")

    candidates: list[Candidate] = []
    unavailable: list[Unavailable] = []
    for structure in STRUCTURES:
        picked, reason = _pick_quotes(structure, quotes, spot, width, targets_by_key.get(structure.key))
        if reason:
            unavailable.append(Unavailable(structure.key, structure.name, reason))
            continue
        legs, bases = [], []
        for quote, spec in zip(picked, structure.legs):
            price, basis = execution_price(quote, spec.action, use_book)
            bases.append(basis)
            legs.append(
                OptionLeg(
                    symbol=quote.symbol,
                    strike=quote.strike,
                    expiry=quote.expiry,
                    kind=spec.kind,
                    action=spec.action,
                    quantity=lot * spec.ratio,
                    premium=price,
                )
            )
        analysis = analyze_payoff(legs)
        assumptions = ["Resultado no vencimento, sem corretagem, emolumentos e impostos."]
        if PriceBasis.CLOSE in bases:
            assumptions.append("Prêmios pelo fechamento do pregão: indicativos, sem garantia de execução.")
        candidates.append(
            Candidate(
                key=structure.key,
                proposal=StrategyProposal(
                    name=structure.name,
                    legs=legs,
                    max_profit=analysis.max_profit,
                    max_loss=analysis.max_loss,
                    breakeven_points=list(analysis.breakevens),
                    risk_reward_ratio=analysis.risk_reward_ratio,
                    rationale=structure.rationale,
                    assumptions=assumptions,
                ),
                quotes=tuple(picked),
                bases=tuple(bases),
            )
        )
    return candidates, unavailable


def fits_regime(key: str, regime: MarketRegime | None, iv_ratio: float | None) -> bool:
    """Compatível com o regime medido. Não é uma recomendação de operar."""
    structure = _BY_KEY[key]
    if structure.long_vol:
        return iv_ratio is not None and iv_ratio <= CHEAP_IV_RATIO
    return regime in structure.regimes
