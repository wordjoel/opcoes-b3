"""Exceções do domínio."""


class DataInsufficientError(Exception):
    """Os dados não permitem concluir. A interface deve mostrar DADOS INSUFICIENTES."""

    label = "DADOS INSUFICIENTES"

    def __init__(self, detail: str, reasons: list[str] | None = None) -> None:
        super().__init__(f"{self.label}: {detail}")
        self.detail = detail
        self.reasons = reasons or []
