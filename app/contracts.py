"""Contratos de resposta da API: procedência, qualidade e rótulo em toda leitura.

Os modelos permitem campos extras para preservar respostas já validadas enquanto o
frontend migra para o envelope. Nenhum número é criado aqui: apenas se padroniza a
declaração do que veio da fonte, do histórico ou do cálculo.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from data.validators import ValidationReport

DataStatus = Literal["REAL", "ATRASADO", "INCOMPLETO", "INDISPONIVEL"]
DataLabel = Literal["REAL", "HISTÓRICO", "CALCULADO", "SIMULADO", "OBSERVADO", "INDISPONÍVEL"]


class ContractModel(BaseModel):
    """Base que não descarta chaves legadas presentes na resposta."""

    model_config = ConfigDict(extra="allow")


class ProvenanceView(ContractModel):
    source: str | None = None
    kind: str | None = None
    collected_at: str | None = None
    market_time: str | None = None
    delay_seconds: float | None = None


class QualityIssueView(ContractModel):
    code: str
    severity: Literal["WARNING", "ERROR"]
    detail: str


class QualityView(ContractModel):
    is_valid: bool
    issues: list[QualityIssueView]


class EnvelopeResponse(ContractModel):
    provenance: ProvenanceView | None = None
    data_status: DataStatus
    quality: QualityView
    missing: list[str]
    label: DataLabel


class ExpirationsResponse(EnvelopeResponse):
    expirations: list[str]


class AssetResponse(EnvelopeResponse):
    quote: dict[str, Any]


class ChainResponse(EnvelopeResponse):
    symbol: str
    expiry: str
    quotes: list[dict[str, Any]]


class ScannerResponse(EnvelopeResponse):
    generated_at: str
    rows: list[dict[str, Any]]
    complete: bool
    incomplete_symbols: list[str]
    timed_out_symbols: list[str]


class StrategiesResponse(EnvelopeResponse):
    symbol: str
    expiry: str
    candidates: list[dict[str, Any]]


class CalendarsResponse(EnvelopeResponse):
    symbol: str
    near: str
    far: str
    candidates: list[dict[str, Any]]


class LabOpportunitiesResponse(EnvelopeResponse):
    generated_at: str
    assets: list[dict[str, Any]]
    opportunities: list[dict[str, Any]]


class LabStrategiesResponse(EnvelopeResponse):
    strategies: list[dict[str, Any]]


class LabStrategyResponse(EnvelopeResponse):
    id: str


class LabRankingResponse(EnvelopeResponse):
    mode: str
    label: DataLabel
    closed: int


class DecisionsResponse(EnvelopeResponse):
    decisions: list[dict[str, Any]]


def provenance_view(provenance: Any = None) -> dict | None:
    """Serializa os cinco campos do `Provenance`, inclusive a idade informada pela fonte."""
    if provenance is None:
        return None
    return {
        "source": provenance.source,
        "kind": provenance.kind.value,
        "collected_at": provenance.collected_at.isoformat(),
        "market_time": provenance.market_time.isoformat(),
        "delay_seconds": provenance.delay_seconds,
    }


def report_view(report: ValidationReport) -> dict:
    return {
        "is_valid": report.is_valid,
        "issues": [{"code": i.code, "severity": i.severity.value, "detail": i.detail} for i in report.issues],
    }


def missing_from_report(report: ValidationReport) -> list[str]:
    return [issue.detail for issue in report.issues if issue.severity.value == "ERROR"]


def quality_from_missing(missing: list[str]) -> dict:
    return {
        "is_valid": not missing,
        "issues": [{"code": "DADOS_INSUFICIENTES", "severity": "ERROR", "detail": detail} for detail in missing],
    }


def combine_quality(*reports: dict) -> dict:
    issues = [issue for report in reports for issue in report["issues"]]
    return {"is_valid": all(report["is_valid"] for report in reports), "issues": issues}


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    return [item for item in items if not (item in seen or seen.add(item))]


def label_from_status(status: str, kind: str | None = None, derived: bool = False, measured: str | None = None) -> DataLabel:
    if measured in ("SIMULADO", "OBSERVADO"):
        return measured
    if status == "INDISPONIVEL":
        return "INDISPONÍVEL"
    if derived:
        return "CALCULADO"
    if kind == "EOD":
        return "HISTÓRICO"
    return "REAL"


def add_envelope(
    payload: dict,
    *,
    data_status: str,
    quality: dict,
    missing: list[str],
    label: str,
    provenance: dict | None = None,
) -> dict:
    """Acrescenta o envelope sem alterar nenhuma chave já consumida pelo frontend."""
    result = dict(payload)
    result.update(
        provenance=provenance,
        data_status=data_status,
        quality=quality,
        missing=dedupe(missing),
        label=label,
    )
    return result
