# Estado dos agentes e do barramento

Auditoria de 03/11/2026.

| Módulo | Situação | Usado pelo app? |
|---|---|---|
| `core/bus.py` | Implementado e testado; memória de um único processo | Não |
| `quant/portfolio.py` | Implementado e testado; sem persistência | Não |
| `agents/risk_manager.py` | Implementado e testado; depende de carteira em memória | Não |
| `agents/orchestrator/supervisor.py` | Implementado e testado; reprova sem veredito explícito | Não |

## Decisão

Os módulos continuam isolados. Na Vercel cada requisição pode cair em outra instância, então eventos e carteira em memória se perderiam, e o log de atividade ficaria vazio ou encenado. O fluxo que o app usa de fato é direto e testado: `app/service.py` chama validadores, `quant/` e `decide()`.

## Condições para integrar

1. Carteira persistida no banco, com operações reais informadas pelo proprietário.
2. Rastreabilidade: cada decisão registrada com os dados que a originaram.
3. Testes de ponta a ponta na arquitetura de produção.

Nenhum desses módulos pode enviar ordens. O fluxo termina em `decision.RESULT`.
