"""Contratos e qualidade de dados."""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.exceptions import DataInsufficientError
from core.types import MarketSnapshot, OptionKind, PriceBar, Provenance, RiskAssessment, SourceKind, StrategyProposal
from data.normalizer import is_stock_symbol, normalize_symbol, parse_option_symbol
from data.providers.base import DataProvider
from data.validators import compare_sources, validate_bars, validate_chain, validate_snapshot
from tests.helpers import NOW, chain, leg, provenance, quote, snapshot

OLD = 21 * 60


class TestContracts:
    def test_snapshot_exige_origem(self):
        with pytest.raises(ValidationError):
            MarketSnapshot(symbol="TEST4", price=40)

    def test_horario_sem_fuso_e_recusado(self):
        with pytest.raises(ValidationError):
            Provenance(source="x", kind=SourceKind.LIVE, collected_at=datetime(2026, 11, 3), market_time=NOW)

    def test_origem_vazia_e_recusada(self):
        with pytest.raises(ValidationError):
            provenance(source="")

    def test_campo_desconhecido_e_recusado(self):
        with pytest.raises(ValidationError):
            MarketSnapshot(symbol="T", price=40, provenance=provenance(), inventado=1)

    def test_modelos_sao_imutaveis(self):
        with pytest.raises(ValidationError):
            snapshot().price = 1

    @pytest.mark.parametrize("price", [0, -1])
    def test_preco_nao_positivo_e_recusado(self, price):
        with pytest.raises(ValidationError):
            snapshot(price=price)

    def test_vwap_e_volume_podem_faltar_sem_virar_zero(self):
        result = snapshot()
        assert result.vwap is None
        assert result.volume is None

    def test_estrategia_representa_ganho_ilimitado(self):
        proposal = StrategyProposal(
            name="Compra de call",
            legs=[leg("BUY", "CALL", 40, 2)],
            max_profit=None,
            max_loss=200,
            breakeven_points=[42],
            risk_reward_ratio=None,
            rationale="teste",
            assumptions=[],
        )
        assert proposal.max_profit is None

    def test_estrategia_exige_pernas(self):
        with pytest.raises(ValidationError):
            StrategyProposal(
                name="x", legs=[], max_profit=1, max_loss=1, breakeven_points=[],
                risk_reward_ratio=1, rationale="", assumptions=[],
            )

    def test_reprovacao_exige_motivo(self):
        with pytest.raises(ValidationError, match="rejection_reason"):
            RiskAssessment(
                is_approved=False, liquidity_score=0.5, stress_test_results={}, warnings=[], final_verdict="não"
            )

    def test_nao_ha_aprovacao_sem_medir_liquidez(self):
        with pytest.raises(ValidationError, match="liquidez"):
            RiskAssessment(
                is_approved=True, liquidity_score=None, stress_test_results={}, warnings=[], final_verdict="sim"
            )

    def test_provedor_precisa_implementar_o_contrato(self):
        class Partial(DataProvider):
            pass

        with pytest.raises(TypeError):
            Partial()


class TestNormalizer:
    def test_normaliza(self):
        assert normalize_symbol(" petr4 ") == "PETR4"
        with pytest.raises(ValueError):
            normalize_symbol("  ")

    def test_identifica_acao(self):
        assert is_stock_symbol("PETR4")
        assert is_stock_symbol("B3SA3")
        assert is_stock_symbol("TAEE11")
        assert not is_stock_symbol("PETRK380")

    @pytest.mark.parametrize(
        ("symbol", "root", "kind", "month"),
        [
            ("PETRA380", "PETR", OptionKind.CALL, 1),
            ("PETRK380", "PETR", OptionKind.CALL, 11),
            ("PETRL380", "PETR", OptionKind.CALL, 12),
            ("PETRM380", "PETR", OptionKind.PUT, 1),
            ("PETRW380", "PETR", OptionKind.PUT, 11),
            ("PETRX380", "PETR", OptionKind.PUT, 12),
            ("B3SAL476", "B3SA", OptionKind.CALL, 12),
            ("PETRK380W2", "PETR", OptionKind.CALL, 11),
        ],
    )
    def test_le_codigo_de_opcao(self, symbol, root, kind, month):
        parsed = parse_option_symbol(symbol)
        assert (parsed.root, parsed.kind, parsed.expiry_month) == (root, kind, month)

    @pytest.mark.parametrize("symbol", ["PETR4", "Petr4C380", "PETRY380", "PETRK"])
    def test_recusa_codigo_invalido(self, symbol):
        with pytest.raises(ValueError):
            parse_option_symbol(symbol)


class TestSnapshotValidation:
    def test_dado_de_teste_e_recusado_por_padrao(self):
        report = validate_snapshot(snapshot(), NOW)
        assert not report.is_valid
        assert "TEST_DATA" in report.codes

    def test_dado_de_teste_so_passa_com_permissao_explicita(self):
        assert validate_snapshot(snapshot(), NOW, allow_test=True).is_valid

    def test_dado_real_recente_passa_sem_permissao(self):
        real = MarketSnapshot(symbol="X", price=1, provenance=provenance(kind=SourceKind.DELAYED, source="fonte"))
        assert validate_snapshot(real, NOW).is_valid

    def test_dado_desatualizado(self):
        report = validate_snapshot(snapshot(age_seconds=OLD), NOW, allow_test=True)
        assert "DATA_STALE" in report.codes

    def test_horario_no_futuro(self):
        report = validate_snapshot(snapshot(age_seconds=-60), NOW, allow_test=True)
        assert "FUTURE_TIMESTAMP" in report.codes

    def test_require_valid_levanta_dados_insuficientes(self):
        with pytest.raises(DataInsufficientError) as error:
            validate_snapshot(snapshot(age_seconds=OLD), NOW, allow_test=True).require_valid()
        assert error.value.reasons


class TestChainValidation:
    def validate(self, *quotes, **kwargs):
        return validate_chain(chain(*quotes, **kwargs), NOW, allow_test=True)

    def test_grade_correta(self):
        report = self.validate(quote())
        assert report.is_valid
        assert len(report.usable_quotes) == 1

    def test_grade_vazia(self):
        assert "EMPTY_CHAIN" in self.validate().codes

    def test_nao_mistura_horarios_entre_ativo_e_opcao(self):
        report = self.validate(quote(age_seconds=300))
        assert not report.is_valid
        assert "TIME_SKEW" in report.codes

    def test_opcao_de_outro_ativo(self):
        assert "UNDERLYING_MISMATCH" in self.validate(quote(underlying="OUTR4")).codes

    @pytest.mark.parametrize(
        ("bad", "code"),
        [
            (dict(bid=None), "MISSING_QUOTE"),
            (dict(ask=None), "MISSING_QUOTE"),
            (dict(bid=0.0), "MISSING_QUOTE"),
            (dict(bid=2.0, ask=1.0), "CROSSED_QUOTE"),
            (dict(expiry=date(2026, 1, 16)), "EXPIRED_OPTION"),
            (dict(bid=50.0, ask=51.0), "PRICE_OUTLIER"),
            (dict(bid=45.0, ask=46.0, kind=OptionKind.PUT), "PRICE_OUTLIER"),
        ],
    )
    def test_cotacao_ruim_sai_das_utilizaveis_e_as_boas_ficam(self, bad, code):
        good = quote(strike=41)
        report = self.validate(quote(**bad), good)
        assert code in report.codes
        assert report.is_valid
        assert report.usable_quotes == (good,)

    def test_sem_nenhuma_cotacao_utilizavel_a_grade_e_invalida(self):
        report = self.validate(quote(bid=None, ask=None))
        assert "NO_USABLE_QUOTES" in report.codes
        assert not report.is_valid


class TestBars:
    def bar(self, day, close=40.0, high=41.0, low=39.0, adjusted=True, symbol="TEST4"):
        return PriceBar(
            symbol=symbol, day=day, open=40, high=high, low=low, close=close,
            adjusted=adjusted, provenance=provenance(),
        )

    def days(self, count):
        return [date(2026, 10, 1) + timedelta(days=i) for i in range(count)]

    def test_serie_correta(self):
        assert validate_bars([self.bar(day) for day in self.days(3)]).is_valid

    def test_vazia(self):
        assert "EMPTY_SERIES" in validate_bars([]).codes

    def test_ohlc_incoerente(self):
        assert "INCONSISTENT_BAR" in validate_bars([self.bar(date(2026, 10, 1), close=50)]).codes

    def test_fora_de_ordem(self):
        first, second = self.days(2)
        assert "UNORDERED_SERIES" in validate_bars([self.bar(second), self.bar(first)]).codes

    def test_lacuna_gera_aviso_sem_invalidar(self):
        report = validate_bars([self.bar(date(2026, 10, 1)), self.bar(date(2026, 10, 20))])
        assert "SERIES_GAP" in report.codes
        assert report.is_valid

    def test_nao_mistura_ajustado_com_nao_ajustado(self):
        first, second = self.days(2)
        assert "MIXED_ADJUSTMENT" in validate_bars([self.bar(first), self.bar(second, adjusted=False)]).codes

    def test_nao_mistura_ativos(self):
        first, second = self.days(2)
        assert "MIXED_SYMBOLS" in validate_bars([self.bar(first), self.bar(second, symbol="OUTR4")]).codes


class TestSourceComparison:
    def test_fontes_coerentes(self):
        assert compare_sources(snapshot(40.0, source="a"), snapshot(40.1, source="b")).is_valid

    def test_divergencia_de_preco(self):
        report = compare_sources(snapshot(40.0, source="a"), snapshot(41.0, source="b"))
        assert "SOURCE_DIVERGENCE" in report.codes

    def test_divergencia_de_horario(self):
        report = compare_sources(snapshot(age_seconds=0), snapshot(age_seconds=600))
        assert "TIME_SKEW" in report.codes


def test_codigo_de_producao_nao_contem_dados_simulados():
    root = Path(__file__).resolve().parent.parent
    for package in ("core", "data", "quant"):
        for path in (root / package).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "SourceKind.TEST" not in text or path.name == "validators.py", path
            assert "mock" not in path.name.lower(), path
