"""Texto para a interface."""


def decimal_comma(formatted: str) -> str:
    """Troca o ponto decimal de um número já formatado pela vírgula do português."""
    return formatted.replace(".", ",")
