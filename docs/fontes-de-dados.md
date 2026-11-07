# Fontes de dados

| Dado | Sem chave da brapi | Com `BRAPI_API_KEY` |
|---|---|---|
| Grade de opções, 8 ativos ou qualquer ação com opções | B3 COTAHIST (grátis, oficial) | brapi; a B3 cobre falhas |
| Vol implícita e delta | Calculados do fechamento (Black-Scholes) | brapi |
| Taxa de juros | Meta Selic, Banco Central (grátis) | brapi |
| Histórico diário | `b3_daily_bars` no Turso, ajustado por proventos com os eventos publicados pela B3 | brapi, ajustado |
| Cotação do dia | brapi sem chave, quando responde; senão, fechamento da B3 | brapi |
| Contratos em aberto | **Indisponível** | brapi |
| Agenda de eventos | brapi, só nos ativos que ela libera sem chave | brapi |

O arquivo da B3 de cada pregão sai por volta das 21h; o cron roda às 22h.

## Comparação com a brapi (dados reais de PETR4)

- 28/10/2026: as 217 séries negociadas têm fechamento, strike e vencimento idênticos.
- Selic e prazo (dias corridos / 365) idênticos.
- Vol implícita: diferença mediana 0 e máxima de 0,17 ponto nas séries a até 20% do dinheiro.
- Vol no dinheiro: a mediana difere até 2,6 pontos, porque a brapi filtra por uma confiança própria que o arquivo não tem. Amostras já gravadas não são sobrescritas.

## Limites

- **Contratos em aberto:** sem eles, a nota de liquidez fica "não medida" e nenhuma estrutura sai como `APROVADA`. A triagem do Laboratório usa só volume e negócios, e a tela avisa.
- **Defasagem:** cotação de fim de dia do mesmo pregão da grade não mede movimento. Ela fica "não medida", nunca 0%. Sem cotação do dia, a entrada em acompanhamento só é aceita até a abertura do pregão seguinte.
- **Proventos:** `data/providers/b3_eventos.py` lê dividendos, JCP, rendimentos, desdobramentos, grupamentos e bonificações na página de empresas listadas da B3 (gratuita) e ajusta os preços antes de cada data ex. Dividendos usam o valor bruto sobre o fechamento da data com. Subscrições não são ajustadas. Se a consulta falhar, ou se a B3 não listar nenhum evento daquele ISIN, o histórico volta sem ajuste e a tela avisa. Cada empresa é consultada no máximo a cada 12 horas; depois de uma falha, a próxima tentativa só acontece 30 minutos depois.
- **Backtest:** o COTAHIST só lista séries negociadas naquele dia, a mesma regra de preço do Laboratório.

## Carga inicial

```
.venv/Scripts/python -m scripts.carregar_historico_b3
```

Só acrescenta; pode repetir sem efeito. Depois, o cron guarda cada novo pregão.
