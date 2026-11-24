# Estado dos agentes e do barramento

Atualizado em 24/11/2026. A auditoria anterior, de 03/11/2026, mantinha os módulos isolados até que três condições fossem cumpridas.

Na atualização de 21/11 (`147c2b7`) entrou o Jarbas com provedor Hermes e diagnóstico de conexão. Ele **explica**, não decide: as ferramentas disponíveis ao assistente são somente leitura e os números exibidos continuam vindo do motor determinístico. As chaves ficam no servidor; o diagnóstico devolve só `ok`, `reachable`, status HTTP e latência, sem URL, chave ou cabeçalho. Falhas transitórias rendem uma repetição curta; erros de autenticação ou cota não são repetidos. O CI (`.github/workflows/ci.yml`) roda pytest, checagem de tipos, Vitest e build.

| Módulo | Situação | Usado pelo app? |
|---|---|---|
| `core/bus.py` | Implementado e testado; um barramento novo por requisição | Sim, na análise de estratégias |
| `quant/portfolio.py` | Implementado e testado; estado refeito do banco a cada uso | Sim, pela carteira |
| `agents/risk_manager.py` | Implementado e testado; avalia contra a carteira gravada | Sim, na análise de estratégias |
| `agents/orchestrator/supervisor.py` | Implementado e testado; reprova sem veredito explícito | Sim, na análise de estratégias |

## Como as condições foram cumpridas

1. **Carteira persistida.** As operações reais informadas pelo proprietário ficam em `portfolio_fills`, e o caixa inicial e o limite por série ficam em `portfolio_settings` (migration `0008_carteira.sql`). Um lançamento errado é anulado, nunca apagado. `app/carteira.py` refaz a carteira em ordem a cada requisição, então qualquer instância da Vercel chega ao mesmo estado.
2. **Rastreabilidade.** Cada decisão mostrada na análise de estratégias é gravada em `decision_log` com os dados que a originaram: pregão, fonte, preço, taxa, prazo, pernas, liquidez, avisos, capital, custos e veredito da carteira. O id é o hash do conteúdo, então a mesma análise repetida não duplica. Consulta em `GET /api/decisions` e na aba Carteira.
3. **Ponta a ponta.** `tests/test_carteira.py` passa pela API com banco real (SQLite, mesmo cliente do Turso) e confirma que outra instância do app lê o mesmo estado.

## Fluxo

`GET /api/assets/{ativo}/strategies` monta as estruturas e a decisão de capital e custos (`quant/risk.decide`). Com a carteira configurada, cada estrutura vira uma intenção no barramento. O `RiskManager` confere o limite por série e a perda máxima contra o caixa, e o supervisor publica `decision.RESULT`. Uma reprovação da carteira reprova a estrutura; uma aprovação dela não aprova nada sozinha. Por fim, tudo é gravado em `decision_log`.

Sem carteira configurada, essa etapa é pulada e a análise segue como antes.

Nenhum desses módulos pode enviar ordens. O fluxo termina em `decision.RESULT`.

## Limites

- O registro do barramento continua em memória e serve só à requisição. A trilha permanente é `decision_log`.
- A carteira não é marcada a mercado: mostra caixa, posições, preço médio e resultado realizado.
- O limite por série conta opções de cada código, sem somar séries do mesmo ativo.
