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

- **Estilo de exercício:** heatmap e estresse usam árvore binomial nas pernas americanas e Black-Scholes nas europeias. A vol implícita vem da fonte, calculada por ela com Black-Scholes-Merton; gregas e probabilidades continuam europeias, e a análise avisa quando há perna americana. Sem dividendos, a call americana vale o mesmo que a europeia; a fonte informa dividendo 0, então dividendo discreto perto do vencimento não é modelado.
- **Dividendos:** tratados como taxa contínua `q`. Dividendos discretos perto do vencimento não são modelados.
- **Taxa de juros:** `r` é obrigatória e não tem valor padrão. Vem da brapi, com a mesma data da grade.
- **Calendário:** `t` é responsabilidade de quem chama. Ainda não há calendário de feriados da B3.
- **Volatilidade constante:** cada cálculo usa uma só `sigma`, sem superfície de volatilidade.
- **Probabilidade de lucro:** é neutra ao risco e lognormal. Mostra o que os parâmetros implicam, não uma previsão, e não é certeza.
- **Payoff:** só no vencimento e para um único vencimento. Calendário e diagonal são recusados até existir um modelo para eles.
- **Custos:** corretagem, emolumentos e impostos não entram no P&L.
- **Volatilidade implícita:** devolve `None` quando nenhuma volatilidade entre 0,01% e 500% explica o preço.

## Estratégias e risco

- **Preço em grade de fim de dia:** todas as pernas usam o fechamento, marcado como indicativo. Bid e ask dessa grade são sobras após o pregão (PETRL497 em 30/10: 607.600 opções negociadas e ofertas finais de 0,25 x 18,50), então não servem de preço nem de medida de liquidez. Os fechamentos das pernas não são simultâneos.
- **Montagem:** as 11 estruturas de um único vencimento buscam o strike mais próximo de um alvo a cada 5% do ativo. Sem strike a até meia largura do alvo, a estrutura é listada como indisponível.
- **Decisão:** `APROVADA` exige regras cumpridas, capital e limite definidos pelo proprietário, e todos os dados presentes. Sem algum deles, `INCOMPLETA`; regra violada, `REPROVADA`. Não é recomendação. Os limites de `RiskLimits` são escolhas iniciais do projeto, não padrões de mercado.
- **Margem:** é calculada pela B3 e pela corretora, e não temos esse dado. Estrutura com perna vendida nunca é aprovada, mesmo com perda máxima definida; só compras a débito, cujo capital necessário é o próprio custo.
- **Defasagem:** se o ativo tiver se movido mais de 3% desde o pregão da grade, todas as estruturas são reprovadas.
- **Liquidez:** 40% contratos em aberto, 40% volume e 20% negócios, com referências de 1.000.000, 100.000 e 100 opções e negócios. O mínimo para aprovar é 0,50.
- **Probabilidade:** usa a média das volatilidades implícitas das pernas.
- **Ainda não calculados:** margem e tamanho de posição.
- **Regime:** médias de 20 e 50 dias, com tendência a partir de 2% de diferença. Volatilidade implícita a 1,3x a histórica ou mais marca `HIGH_VOL`. Compatível com o regime não é recomendação.

## Delta, eventos, estrutura e contratos em aberto

- **Strikes por delta:** travas, strangle e iron condor escolhem o delta informado pela fonte mais próximo do alvo do perfil (`PROFILES`), até 0,10 de distância, entre séries com pelo menos 5.000 opções negociadas e 10.000 em aberto. Os alvos são pontos de partida, sem backtest que os valide. Sem série adequada, a estrutura é indisponível: nenhum strike é trocado para fazê-la caber.
- **Probabilidade dentro do dinheiro:** neutra ao risco, com a vol implícita da perna. Não é previsão.
- **Eventos:** datas da fonte. Evento até o vencimento gera aviso; resultado antes de um vencimento a menos de 7 dias reprova. A estrutura não é alterada para "absorver" o evento: alargar a trava aumenta a perda máxima.
- **Estrutura:** topos e fundos diários com 5 barras de cada lado, rompidos pelo fechamento. Descreve o passado e não foi testada como sinal.
- **Contratos em aberto:** totais e variação do vencimento. Não indicam quem abriu ou fechou posição, então o app não conclui "squeeze".

## IV Rank

- **Medida:** mediana das vols implícitas com confiança alta ou média da fonte, a até 5% do ativo, no vencimento mensal a pelo menos 20 dias. A mesma medida vale para o valor atual e para o histórico.
- **Histórico:** amostra semanal de até 52 semanas, guardada em `iv_history`. Só há IV Rank com pelo menos 26 amostras; antes disso a tela mostra quantas já existem.
- **Limites:** o vencimento de referência muda ao longo do ano. Em datas passadas não é possível confirmar que a série negociou naquele dia, e a vol pode vir de um preço antigo. Feriado sem pregão não gera amostra. Os cortes de 80 e 20 são convenção: indicam a posição da vol, não uma operação.

## Mapa de resultado

Valor pelo modelo europeu hoje, com a vol implícita de cada perna, menos o prêmio de montagem. Não usa Monte Carlo, pois cada célula tem solução direta.

## Regra de dados

Dados com `SourceKind.TEST` existem apenas em `tests/` e são recusados pelos validadores, salvo com `allow_test=True`. Dado inválido ou histórico curto levanta `DataInsufficientError`, com a mensagem `DADOS INSUFICIENTES`.
