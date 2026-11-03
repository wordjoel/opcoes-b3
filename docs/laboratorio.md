# Laboratório de Estratégias

Testa se as estratégias propostas funcionariam. É exclusivamente analítico: não há rota de ordens.

## Quem faz o quê

| Papel da missão | Onde está | Observação |
|---|---|---|
| Scanner | `app/lab.py: discover` | Varre a lista de ativos acompanhados e informa liquidez |
| Research | `quant/lab.py: vertical_scan` | Só combinações de travas; não há pesquisa externa nem IA |
| Strategist | `quant/strategies.py`, `vertical_scan` | Regras determinísticas |
| Risk Analyst | `quant/risk.py: assess_risk, decide` | Sem capital ou margem, nada é aprovado |
| Backtest | `app/lab.py: run_backtest` | Resumível |
| Monitor | `app/lab.py: monitor` | A cada pregão, pelo cron ou manualmente |
| Performance | `quant/lab.py: rank_groups` | Mediana, com mínimo de 20 datas de entrada |
| Coordinator | `app/lab.py` e rotas | Funções, sem processo próprio |

Os "agentes" do ranking são as cinco regras que propõem estruturas de fato: `regra_5pct`, `delta_conservador`, `delta_moderado`, `delta_agressivo` e `varredura_vertical`.

## Os quatro retornos

| Retorno | Significado |
|---|---|
| Potencial | Máximo que a estrutura permite no vencimento |
| Teórico | Valor esperado pelo modelo lognormal neutro ao risco, com a vol da entrada |
| Simulado | Backtest: preços históricos reais, com execução presumida no fechamento |
| Observado | Acompanhamento: preços reais posteriores à entrada, sem execução |

Nenhum deles é lucro realizado. Simulado e observado nunca se misturam no ranking.

## Regras contra resultados falsos

- **Sem olhar o futuro:** a proposta usa só a grade do dia da entrada, e um teste troca os preços futuros para provar que as pernas não mudam.
- **Preço do dia:** a perna só tem preço se negociou naquele pregão. Faltando alguma, a marcação fica incompleta e não há resultado.
- **Vencimento:** a liquidação é pelo preço do ativo.
- **Entrada à frente:** é recusada se o ativo já se moveu mais de 3% desde a grade.
- **O cliente não informa preços:** a estrutura é refeita no servidor.
- **Varredura:** recusa pares com vols distantes, poucos negócios ou risco ínfimo frente à largura. Sem isso, ela escolhia preços velhos e mostrava retornos impossíveis.

## Limitações

- **Execução:** só há fechamento. O bid e o ask históricos são sobras de ofertas, então não provam que a operação seria possível ao preço usado, e esse viés é otimista.
- **Fechamentos não simultâneos:** as pernas podem ter negociado em horários diferentes, inclusive nas estruturas selecionadas.
- **Alvo e stop:** avaliados nas datas marcadas, não dentro do dia. O backtest marca só em 1, 3, 5, 10, 15 e 30 pregões, então o drawdown é aproximado.
- **Custos:** só entram se informados.
- **Monitoramento:** diário, porque a fonte é de fim de dia.
- **Cobertura:** a varredura usa a lista de ativos acompanhados. Sem token da brapi, só a PETR4 tem opções.
- **Margem:** não modelada.
- **Sobreajuste:** comparar muitas regras no mesmo período favorece a sorte. Um bom resultado pede confirmação no acompanhamento.
