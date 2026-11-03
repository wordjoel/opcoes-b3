"""Carteira: caixa, posições e resultado realizado a partir das operações informadas.

Segue a convenção do projeto (docs/quant-convencoes.md): `quantity` é a quantidade de
opções, e não de lotes, e o preço é em R$ por opção. Por isso não há multiplicador 100.
Custos e impostos não entram.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from core.exceptions import DataInsufficientError


@dataclass(frozen=True)
class Position:
    symbol: str
    # Negativa quando vendida.
    quantity: int
    avg_entry_price: float


@dataclass(frozen=True)
class FillResult:
    # Resultado realizado por esta operação, em R$.
    realized_pnl: float
    # Quantidade da posição depois da operação; 0 = zerada.
    new_quantity: int


@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0

    def apply_fill(self, symbol: str, quantity: int, price: float, is_buy: bool) -> FillResult:
        """`quantity` é sempre positiva; o lado vem de `is_buy`. Dado inválido não altera a carteira."""
        if quantity <= 0:
            raise ValueError("Quantidade precisa ser positiva")
        if price < 0:
            raise ValueError("Preço não pode ser negativo")

        signed = quantity if is_buy else -quantity
        existing = self.positions.get(symbol)
        old_quantity = existing.quantity if existing else 0
        old_price = existing.avg_entry_price if existing else 0.0
        new_quantity = old_quantity + signed

        realized = 0.0
        if old_quantity == 0 or (old_quantity > 0) == is_buy:
            # Abre ou aumenta: preço médio ponderado.
            new_price = (abs(old_quantity) * old_price + quantity * price) / abs(new_quantity)
        else:
            # Reduz, zera ou inverte: só a parte que fecha realiza resultado.
            closed = min(abs(old_quantity), quantity)
            direction = 1 if old_quantity > 0 else -1
            realized = (price - old_price) * closed * direction
            # O que passar de zero é posição nova, ao preço desta operação.
            crossed = quantity > abs(old_quantity)
            new_price = price if crossed else old_price

        self.cash -= signed * price
        self.realized_pnl += realized
        if new_quantity == 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = Position(symbol, new_quantity, new_price)
        return FillResult(realized, new_quantity)

    def equity(self, prices: Mapping[str, float]) -> float:
        """Caixa + posições a mercado. Sem o preço de alguma posição, não há como concluir."""
        missing = sorted(symbol for symbol in self.positions if symbol not in prices)
        if missing:
            raise DataInsufficientError("carteira sem preço para todas as posições", missing)
        return self.cash + sum(p.quantity * prices[p.symbol] for p in self.positions.values())
