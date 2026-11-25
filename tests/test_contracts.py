"""Envelope: rótulo e procedência não podem inventar estado de dado."""

from datetime import datetime, timedelta, timezone

from app.contracts import label_from_status, provenance_view
from core.types import Provenance, SourceKind

NOW = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)


class TestLabel:
    def test_indisponivel_prevalece_sobre_medido_e_calculado(self):
        assert label_from_status("INDISPONIVEL", kind="EOD", derived=True, measured="OBSERVADO") == "INDISPONÍVEL"
        assert label_from_status("INDISPONIVEL", measured="SIMULADO") == "INDISPONÍVEL"

    def test_demais_rotulos_guardam_a_origem(self):
        assert label_from_status("REAL", kind="EOD") == "HISTÓRICO"
        assert label_from_status("REAL", kind="LIVE") == "REAL"
        assert label_from_status("REAL", derived=True) == "CALCULADO"
        assert label_from_status("REAL", measured="OBSERVADO") == "OBSERVADO"


class TestProvenance:
    def test_atraso_e_calculado_quando_a_fonte_nao_informa(self):
        provenance = Provenance(
            source="COTAHIST",
            kind=SourceKind.EOD,
            collected_at=NOW,
            market_time=NOW - timedelta(minutes=42),
        )
        assert provenance_view(provenance)["delay_seconds"] == 42 * 60

    def test_valor_informado_pela_fonte_prevalece(self):
        provenance = Provenance(
            source="brapi",
            kind=SourceKind.LIVE,
            collected_at=NOW,
            market_time=NOW - timedelta(minutes=42),
            delay_seconds=7.5,
        )
        assert provenance_view(provenance)["delay_seconds"] == 7.5

    def test_horario_de_mercado_no_futuro_nao_gera_atraso_negativo(self):
        provenance = Provenance(
            source="brapi",
            kind=SourceKind.LIVE,
            collected_at=NOW,
            market_time=NOW + timedelta(minutes=5),
        )
        assert provenance_view(provenance)["delay_seconds"] == 0.0
