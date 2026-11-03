"""Casos de referência independentes do próprio código: valores publicados, relações
teóricas, diferenças finitas e simulação."""

from math import exp, log, sqrt

import numpy as np
import pytest
from scipy.special import ndtr

from core.exceptions import DataInsufficientError
from core.types import OptionKind
from quant.greeks import option_greeks
from quant.payoff import analyze_payoff, net_premium, position_pnl, probability_of_profit
from quant.pricing.black_scholes import option_price
from quant.volatility import ewma_volatility, historical_volatility, implied_volatility
from tests.helpers import EXPIRY, leg

CALL, PUT = OptionKind.CALL, OptionKind.PUT


class TestPricing:
    def test_exemplo_classico_s100(self):
        assert option_price(CALL, 100, 100, 1, 0.05, 0.2) == pytest.approx(10.4506, abs=1e-4)
        assert option_price(PUT, 100, 100, 1, 0.05, 0.2) == pytest.approx(5.5735, abs=1e-4)

    def test_exemplo_de_hull(self):
        # Hull, Options, Futures and Other Derivatives: S=42, K=40, r=10%, vol=20%, T=0,5.
        assert option_price(CALL, 42, 40, 0.5, 0.10, 0.2) == pytest.approx(4.76, abs=0.005)
        assert option_price(PUT, 42, 40, 0.5, 0.10, 0.2) == pytest.approx(0.81, abs=0.005)

    @pytest.mark.parametrize("q", [0.0, 0.06])
    def test_paridade_put_call(self, q):
        s, k, t, r, sigma = 38.5, 40, 0.1, 0.15, 0.3
        difference = option_price(CALL, s, k, t, r, sigma, q) - option_price(PUT, s, k, t, r, sigma, q)
        assert difference == pytest.approx(s * exp(-q * t) - k * exp(-r * t), abs=1e-10)

    def test_no_vencimento_vale_o_intrinseco(self):
        assert option_price(CALL, 42, 40, 0, 0.1, 0.2) == 2
        assert option_price(CALL, 38, 40, 0, 0.1, 0.2) == 0
        assert option_price(PUT, 38, 40, 0, 0.1, 0.2) == 2

    def test_volatilidade_zero_vale_o_termo_descontado(self):
        assert option_price(CALL, 42, 40, 0.5, 0.1, 0) == pytest.approx(42 - 40 * exp(-0.05))

    @pytest.mark.parametrize("args", [(0, 40, 0.2), (40, 0, 0.2), (40, 40, -0.1)])
    def test_recusa_entradas_invalidas(self, args):
        s, k, sigma = args
        with pytest.raises(ValueError):
            option_price(CALL, s, k, 1, 0.1, sigma)


class TestGreeks:
    def test_valores_de_referencia(self):
        greeks = option_greeks(CALL, 100, 100, 1, 0.05, 0.2)
        assert greeks.delta == pytest.approx(0.6368, abs=1e-4)
        assert greeks.gamma == pytest.approx(0.01876, abs=1e-5)
        assert greeks.vega == pytest.approx(37.524, abs=1e-3)
        assert greeks.theta == pytest.approx(-6.414, abs=1e-3)
        assert greeks.rho == pytest.approx(53.232, abs=1e-3)

    @pytest.mark.parametrize("kind", [CALL, PUT])
    @pytest.mark.parametrize("q", [0.0, 0.06])
    def test_conferem_com_diferencas_finitas(self, kind, q):
        s, k, t, r, sigma = 38.5, 40, 0.2, 0.15, 0.3
        h = 1e-4
        price = lambda s=s, t=t, r=r, sigma=sigma: option_price(kind, s, k, t, r, sigma, q)  # noqa: E731
        greeks = option_greeks(kind, s, k, t, r, sigma, q)
        assert greeks.delta == pytest.approx((price(s=s + h) - price(s=s - h)) / (2 * h), abs=1e-6)
        assert greeks.gamma == pytest.approx((price(s=s + h) - 2 * price() + price(s=s - h)) / h**2, abs=1e-4)
        assert greeks.vega == pytest.approx((price(sigma=sigma + h) - price(sigma=sigma - h)) / (2 * h), abs=1e-5)
        assert greeks.rho == pytest.approx((price(r=r + h) - price(r=r - h)) / (2 * h), abs=1e-5)
        assert greeks.theta == pytest.approx(-(price(t=t + h) - price(t=t - h)) / (2 * h), abs=1e-4)

    def test_conversoes_de_unidade(self):
        greeks = option_greeks(CALL, 100, 100, 1, 0.05, 0.2)
        assert greeks.theta_per_business_day == pytest.approx(greeks.theta / 252)
        assert greeks.vega_per_vol_point == pytest.approx(greeks.vega / 100)

    def test_vencida_nao_divide_por_zero(self):
        assert option_greeks(CALL, 42, 40, 0, 0.1, 0.2).delta == 1
        assert option_greeks(PUT, 42, 40, 0, 0.1, 0.2).delta == 0


class TestVolatility:
    @pytest.mark.parametrize("kind", [CALL, PUT])
    @pytest.mark.parametrize("strike", [30, 38.5, 50])
    def test_recupera_a_volatilidade_implicita(self, kind, strike):
        price = option_price(kind, 38.5, strike, 0.1, 0.15, 0.37)
        assert implied_volatility(kind, price, 38.5, strike, 0.1, 0.15) == pytest.approx(0.37, abs=1e-6)

    def test_preco_impossivel_devolve_none(self):
        assert implied_volatility(CALL, 100, 38.5, 42, 0.1, 0.15) is None
        assert implied_volatility(CALL, 0, 38.5, 42, 0.1, 0.15) is None
        assert implied_volatility(CALL, 1, 38.5, 42, 0, 0.15) is None

    def test_historica_recupera_a_vol_de_uma_serie_simulada(self):
        rng = np.random.default_rng(7)
        daily = 0.30 / sqrt(252)
        closes = 40 * np.exp(np.cumsum(rng.normal(0, daily, 20_000)))
        assert historical_volatility(closes) == pytest.approx(0.30, abs=0.01)

    def test_historica_em_serie_conhecida(self):
        closes = [100, 110, 100, 110, 100]
        returns = np.diff(np.log(closes))
        expected = np.std(returns, ddof=1) * sqrt(252)
        assert historical_volatility(closes, min_observations=4) == pytest.approx(expected)

    def test_ewma_com_retorno_constante(self):
        step = 0.01
        closes = 100 * np.exp(step * np.arange(30))
        assert ewma_volatility(closes) == pytest.approx(step * sqrt(252))

    def test_ewma_reage_mais_ao_choque_recente_que_a_historica(self):
        rng = np.random.default_rng(3)
        calm = 100 * np.exp(np.cumsum(rng.normal(0, 0.005, 100)))
        shocked = np.append(calm, calm[-1] * 0.9)
        assert ewma_volatility(shocked) > historical_volatility(shocked)

    def test_historico_curto_e_dados_insuficientes(self):
        with pytest.raises(DataInsufficientError, match="DADOS INSUFICIENTES"):
            historical_volatility([40, 41, 42])
        with pytest.raises(DataInsufficientError):
            ewma_volatility([40, 41, 42])

    @pytest.mark.parametrize("closes", [[40, 0] * 15, [40, float("nan")] * 15])
    def test_preco_invalido_e_recusado(self, closes):
        with pytest.raises(ValueError):
            historical_volatility(closes)


class TestPayoff:
    def test_compra_de_call(self):
        result = analyze_payoff([leg("BUY", "CALL", 40, 2)])
        assert result.max_profit is None
        assert result.max_loss == pytest.approx(200)
        assert result.breakevens == pytest.approx((42,))
        assert result.risk_reward_ratio is None

    def test_compra_de_put_tem_ganho_limitado_ao_strike(self):
        result = analyze_payoff([leg("BUY", "PUT", 40, 2)])
        assert result.max_profit == pytest.approx(3800)
        assert result.max_loss == pytest.approx(200)
        assert result.breakevens == pytest.approx((38,))

    def test_call_vendida_tem_perda_ilimitada(self):
        result = analyze_payoff([leg("SELL", "CALL", 40, 1)])
        assert result.max_loss is None
        assert result.max_profit == pytest.approx(100)

    def test_trava_de_alta(self):
        legs = [leg("BUY", "CALL", 38, 1.5), leg("SELL", "CALL", 40, 0.7)]
        result = analyze_payoff(legs)
        assert net_premium(legs) == pytest.approx(80)
        assert result.max_loss == pytest.approx(80)
        assert result.max_profit == pytest.approx(120)
        assert result.breakevens == pytest.approx((38.8,))
        assert result.risk_reward_ratio == pytest.approx(1.5)

    def test_trava_de_baixa(self):
        result = analyze_payoff([leg("BUY", "PUT", 40, 1.5), leg("SELL", "PUT", 38, 0.7)])
        assert result.max_loss == pytest.approx(80)
        assert result.max_profit == pytest.approx(120)
        assert result.breakevens == pytest.approx((39.2,))

    def test_straddle(self):
        result = analyze_payoff([leg("BUY", "CALL", 38, 1), leg("BUY", "PUT", 38, 1)])
        assert result.max_profit is None
        assert result.max_loss == pytest.approx(200)
        assert result.breakevens == pytest.approx((36, 40))

    def test_strangle(self):
        result = analyze_payoff([leg("BUY", "PUT", 36, 1), leg("BUY", "CALL", 40, 1)])
        assert result.max_loss == pytest.approx(200)
        assert result.breakevens == pytest.approx((34, 42))

    def test_iron_condor(self):
        legs = [
            leg("BUY", "PUT", 34, 0.2),
            leg("SELL", "PUT", 36, 0.6),
            leg("SELL", "CALL", 41, 0.6),
            leg("BUY", "CALL", 43, 0.2),
        ]
        result = analyze_payoff(legs)
        assert net_premium(legs) == pytest.approx(-80)
        assert result.max_profit == pytest.approx(80)
        assert result.max_loss == pytest.approx(120)
        assert result.breakevens == pytest.approx((35.2, 41.8))

    def test_butterfly(self):
        legs = [leg("BUY", "CALL", 38, 3), leg("SELL", "CALL", 40, 1.5, 200), leg("BUY", "CALL", 42, 0.5)]
        result = analyze_payoff(legs)
        assert result.max_loss == pytest.approx(50)
        assert result.max_profit == pytest.approx(150)
        assert result.breakevens == pytest.approx((38.5, 41.5))

    def test_quantidade_escala_premio_e_resultado(self):
        # Regressão: o prêmio precisa multiplicar pela quantidade de cada perna.
        one = analyze_payoff([leg("BUY", "CALL", 40, 2, 100)])
        three = analyze_payoff([leg("BUY", "CALL", 40, 2, 300)])
        assert three.max_loss == pytest.approx(one.max_loss * 3)
        assert three.breakevens == pytest.approx(one.breakevens)

    def test_pnl_e_vetorizado(self):
        pnl = position_pnl([leg("BUY", "CALL", 40, 2)], np.array([30.0, 40.0, 50.0]))
        assert pnl == pytest.approx([-200, -200, 800])

    def test_pnl_zero_constante_nao_tem_breakeven(self):
        assert analyze_payoff([leg("BUY", "CALL", 40, 1), leg("SELL", "CALL", 40, 1)]).breakevens == ()

    def test_recusa_mais_de_um_vencimento(self):
        other = EXPIRY.replace(year=EXPIRY.year + 1)
        with pytest.raises(ValueError, match="único vencimento"):
            analyze_payoff([leg("BUY", "CALL", 40, 2), leg("SELL", "CALL", 40, 1, expiry=other)])


class TestProbability:
    INPUTS = dict(spot=38.0, sigma=0.3, t=0.1, r=0.15)

    def test_formula_fechada_na_compra_de_call(self):
        d2 = (log(38 / 40) + (0.15 - 0.045) * 0.1) / (0.3 * sqrt(0.1))
        assert probability_of_profit([leg("BUY", "CALL", 39, 1)], **self.INPUTS) == pytest.approx(float(ndtr(d2)))

    def test_posicoes_opostas_somam_um(self):
        long = probability_of_profit([leg("BUY", "CALL", 39, 1)], **self.INPUTS)
        short = probability_of_profit([leg("SELL", "CALL", 39, 1)], **self.INPUTS)
        assert long + short == pytest.approx(1)

    @pytest.mark.parametrize(
        "legs",
        [
            [leg("BUY", "PUT", 34, 0.2), leg("SELL", "PUT", 36, 0.6), leg("SELL", "CALL", 41, 0.6), leg("BUY", "CALL", 43, 0.2)],
            [leg("BUY", "CALL", 38, 1), leg("BUY", "PUT", 38, 1)],
            [leg("BUY", "CALL", 38, 1.5), leg("SELL", "CALL", 40, 0.7)],
        ],
    )
    def test_coincide_com_monte_carlo(self, legs):
        rng = np.random.default_rng(11)
        z = rng.standard_normal(1_000_000)
        prices = 38 * np.exp((0.15 - 0.045) * 0.1 + 0.3 * sqrt(0.1) * z)
        simulated = float(np.mean(position_pnl(legs, prices) > 0))
        assert probability_of_profit(legs, **self.INPUTS) == pytest.approx(simulated, abs=0.002)

    def test_recusa_parametros_invalidos(self):
        with pytest.raises(ValueError):
            probability_of_profit([leg("BUY", "CALL", 39, 1)], spot=38, sigma=0, t=0.1, r=0.15)
