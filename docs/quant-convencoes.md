# Convenções e limitações do motor quantitativo

## Unidades

| Grandeza | Convenção |
|---|---|
| `t` | Anos |
| `r`, `q`, `sigma` | Decimal anual (0,15 = 15%), composição contínua |
| Ano de negociação | 252 dias úteis |
| `quantity` | Opções por perna; na B3, um lote padrão de ações equivale a 100 |
| `premium` | R$ por opção |
| P&L, ganho e perda máximos | R$ da posição inteira |
| `None` em `max_profit` ou `max_loss` | Ilimitado |
| `delta`, `gamma` | Por R$ 1,00 no ativo, por opção |
| `theta` | Por ano; `theta_per_business_day` divide por 252 |
| `vega`, `rho` | Por 1,00; `vega_per_vol_point` e `rho_per_rate_point` dividem por 100 |

## Limitações

- **Estilo de exercício:** o modelo é europeu. Com dividendos ou puts muito dentro do dinheiro, o valor de uma opção americana pode ser maior. `OptionQuote.style` guarda o estilo, mas o preço ainda não o usa.
- **Dividendos:** tratados como taxa contínua `q`. Dividendos discretos perto do vencimento não são modelados.
- **Taxa de juros:** `r` é obrigatória e não tem valor padrão, pois precisa de fonte e data. A fonte ainda não existe.
- **Calendário:** `t` é responsabilidade de quem chama. Ainda não há calendário de feriados da B3.
- **Volatilidade constante:** cada cálculo usa uma só `sigma`, sem superfície de volatilidade.
- **Probabilidade de lucro:** é neutra ao risco e lognormal. Mostra o que os parâmetros implicam, não uma previsão, e não é certeza.
- **Payoff:** só no vencimento e para um único vencimento. Calendário e diagonal são recusados até existir um modelo para eles.
- **Custos:** corretagem, emolumentos e impostos não entram no P&L.
- **Volatilidade implícita:** devolve `None` quando nenhuma volatilidade entre 0,01% e 500% explica o preço.

## Regra de dados

Dados com `SourceKind.TEST` existem apenas em `tests/` e são recusados pelos validadores, salvo com `allow_test=True`. Dado inválido ou histórico curto levanta `DataInsufficientError`, com a mensagem `DADOS INSUFICIENTES`.
