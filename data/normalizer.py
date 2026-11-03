"""Padronização de símbolos da B3."""

import re
from dataclasses import dataclass

from core.types import OptionKind

_STOCK = re.compile(r"^[A-Z0-9]{4}\d{1,2}$")
_OPTION = re.compile(r"^([A-Z0-9]{4})([A-X])(\d{1,4})(W\d|[A-Z])?$")


@dataclass(frozen=True)
class ParsedOptionSymbol:
    root: str
    kind: OptionKind
    # 1 = janeiro, 12 = dezembro.
    expiry_month: int


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("Símbolo vazio")
    return normalized


def is_stock_symbol(symbol: str) -> bool:
    return _STOCK.fullmatch(normalize_symbol(symbol)) is not None


def parse_option_symbol(symbol: str) -> ParsedOptionSymbol:
    """Calls usam as letras A a L (jan a dez) e puts, M a X (jan a dez)."""
    normalized = normalize_symbol(symbol)
    match = _OPTION.fullmatch(normalized)
    if match is None:
        raise ValueError(f"Código de opção inválido: {symbol!r}")
    root, letter, _, _ = match.groups()
    index = ord(letter) - ord("A")
    if index < 12:
        return ParsedOptionSymbol(root, OptionKind.CALL, index + 1)
    return ParsedOptionSymbol(root, OptionKind.PUT, index - 11)
