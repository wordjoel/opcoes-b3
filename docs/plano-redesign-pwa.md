# Plano técnico — Redesign da interface, experiência financeira e PWA

Data: 24/11/2026. Status: **auditoria concluída; aguardando aprovação para alterações estruturais**.

Referência visual: InfoMoney (conceitos de hierarquia, cards e clareza financeira). Identidade própria: Newsprint/B3 Opções Pro. Nenhum logotipo, texto, componente proprietário ou conteúdo do InfoMoney será copiado.

## 0. Responsabilidades

| Responsável | Escopo |
|---|---|
| Google AI Studio | Concepção visual, componentes, navegação, tokens de design, layout desktop/tablet/celular e estrutura PWA do lado do cliente. |
| OpenCode | Auditoria de infraestrutura, contratos de API, integração com serviços existentes, persistência, agendamento, segurança e funcionamento dos módulos. |

Este documento é a entrega da parte OpenCode. Nenhuma estrutura de código foi alterada para produzir este plano.

## 1. Auditoria da base existente

### 1.1 Estado geral

- Branch local `feature/b3-intelligence-core` alinhada a `origin/main` no commit `036a7f9`.
- Produção: `b3-opcoes-pro.vercel.app`, deploy `dpl_Npr2kLqkjzWfUa7L8WViMiFmFZfR`.
- Suíte validada em 24/11: **616 testes Python**, **81 testes Vitest**, `tsc --noEmit` e `vite build` sem erros.
- Stack: React 19 + Vite/Tailwind 4 (`src/`), FastAPI (`app/` + `api/index.py`), Turso/SQLite (`db/`), motor determinístico (`quant/`), contratos Pydantic (`core/types.py`).
- O projeto é **somente análise**: não há rota de ordens e testes garantem 404 em `/api/orders`, `/api/ordens`, `/api/order`, `/api/lab/execute`.

### 1.2 Mapa dos módulos pedidos (A–I)

| Módulo | Hoje | Falta | Natureza do trabalho |
|---|---|---|---|
| A. Dashboard — Central de Mercado | `Dashboard.tsx`: cotação, `DataStatusBadge`, lista de ativos, candles e HV; `Scanner.tsx` com variação e status | Grade de KPIs, cards de oportunidades, agregado de posições monitoradas, feed textual com procedência | UI + reorganização de API |
| B. Central Hermes | Jarbas (`Jarbas.tsx`) com texto/voz e provedores de IA; `app/jarbas/*`; `/api/jarbas/diagnose` | Tela de agentes, registro de tarefas, orquestração, aprovação de novos agentes | **Backend novo + UI nova** |
| C. Scanner B3 | `Scanner.tsx`: varredura, watchlist, avisos de incompleteza, sinais | Classificação visual mais clara; proveniência completa por linha | UI + ajuste de contrato |
| D. Estratégias e travas | `StrategyView.tsx`: 11 estruturas, grade, gregas, custos, ranking, calendário, guia | Nada estrutural; apenas nova apresentação | UI |
| E. Gráfico de payoff | `PayoffMap.tsx` interativo (slider de preço, prazo e vol), dentro de Estratégias | Aba própria e visual mais gráfico | UI |
| F. Monitoramento de operações | `Alerts.tsx` (sinais efêmeros), `Lab.tsx` (monitor com marcações), `AppStatus.tsx` (PWA/online) | Alertas persistidos, carteira marcada a mercado, alertas de risco e sugestões de saída com histórico | **Backend novo + UI** |
| G. Previsto versus Realizado | `Lab.tsx` separa POTENCIAL/TEÓRICO/SIMULADO/OBSERVADO; `quant/lab.py` tem `book_pnl` e `mark_pnl` | Tela comparativa consolidada; `pnl_book_unit` não é serializado; decisões sem desfecho observado | Backend + UI |
| H. Áudio e vídeo | Web Speech real em `src/lib/voice.ts` e `Jarbas.tsx` (mic, TTS frase a frase, mute, voz pt-BR) | Vídeo não existe (sem `<video>`, `getUserMedia` ou player) | UI + decisão de escopo |
| I. Configurações | Espalhado: risco/custo em `StrategyView.tsx`, Jarbas em modal, tema no Masthead, carteira em `Carteira.tsx`, watchlist no Scanner | Tela única agregando as rotas existentes | UI + rota agregada opcional |

**Conclusão:** o núcleo funcional (C, D, E, parte de A/F/G/H/I) já existe e não deve ser reescrito. O que falta de verdade é (1) contrato de dados consistente, (2) alertas e marcação a mercado persistidos, (3) orquestração/agentes, (4) camada visual nova.

### 1.3 APIs disponíveis

`app/main.py` expõe **39 rotas** sob `/api`. Todas exigem sessão, exceto `/api/session`, `/api/login`, `/api/logout` e `/api/cron/scan` (autenticado por `Authorization: Bearer CRON_SECRET`).

| Domínio | Rotas |
|---|---|
| Sessão | `GET /session`, `POST /login`, `POST /logout` |
| Configurações | `GET/PUT /settings/costs`, `GET/PUT /settings/risk`, `GET /status` |
| Mercado | `GET/POST /watchlist`, `DELETE /watchlist/{symbol}`, `GET /scanner`, `GET /cron/scan`, `GET /assets/{symbol}`, `GET /assets/{symbol}/expirations`, `GET /assets/{symbol}/chain` |
| Estratégias | `GET /assets/{symbol}/strategies`, `GET /assets/{symbol}/calendars` |
| Laboratório | `GET /lab/opportunities`, `GET/POST /lab/strategies`, `GET /lab/strategies/{identity}`, `POST /lab/monitor`, `POST /lab/backtests`, `GET /lab/ranking` |
| Carteira e decisões | `GET /portfolio`, `PUT /portfolio/settings`, `POST /portfolio/fills`, `POST /portfolio/fills/{identity}/void`, `GET /decisions` |
| Jarbas | `GET /jarbas/status`, `GET /jarbas/diagnose`, `GET/PUT /jarbas/settings`, `GET /jarbas/models`, `GET /jarbas/conversations`, `GET/DELETE /jarbas/conversations/{identity}`, `POST /jarbas/chat` |

Atenções de contrato:

- **Nenhuma rota declara `response_model`** e o OpenAPI está desligado (`app/main.py:192`). O front recebe `dict` e confia nele (`api.ts:25-48` faz `body as T`).
- `GET /assets/{symbol}/strategies` **grava** `decision_log` (`app/main.py:460-461`). Consulta e comando precisam ser separados antes de o novo front passar a chamá-la com mais frequência.
- `/scanner` e `/chain` também gravam cache; são leituras com efeito colateral controlado.
- Proveniência é emitida de forma desigual: `data_status` só em scanner e ativo; `quality` em ativo, grade e estratégias; `delay_seconds` nunca sai do backend (`app/service.py:65-71`); calendário não tem `quality`.

### 1.4 Dados: real, histórico, calculado, simulado, observado

- `Provenance` (`core/types.py:55-62`) exige `source`, `kind`, `collected_at`, `market_time`. `SourceKind = LIVE | DELAYED | EOD | CACHE | TEST`; `TEST` é recusado em produção (`data/validators.py:58-70`).
- `data_status` (`app/service.py:55-62`): `REAL`, `ATRASADO` (>20 min), `INCOMPLETO`, `INDISPONÍVEL`.
- Rótulos `REAL / HISTÓRICO / CALCULADO / INDISPONÍVEL` hoje existem **como texto** nas ferramentas do Jarbas (`app/jarbas/tools.py:45,79-108`), não como campo estruturado.
- `SIMULADO` versus `OBSERVADO` existe em `returns.measured_label` (`app/lab.py:538,612-619`).
- Invariantes que o redesign não pode violar:
  - Nenhum número inventado; ausência vira `DADOS INSUFICIENTES`.
  - Nenhum fallback simulado em produção (teste varre `core`, `data`, `quant` contra `SourceKind.TEST`/mock).
  - Simulado nunca é apresentado como observado.
  - Sem aprovação explícita de risco e sem dados completos, nada é `APROVADA`.
  - Carteira pode reprovar, nunca aprovar sozinha (`app/carteira.py:144-153`).
  - Calendário/diagonal nunca é aprovado (`app/service.py:422-424,489`).

### 1.5 Persistência existente (Turso/SQLite)

Migrations `0001` a `0009`, aplicadas manualmente por `python -m db.migrate`:

| Migration | Conteúdo |
|---|---|
| 0001 | `watchlist`, `provider_cache`, `login_failures`, `iv_history` |
| 0003 | `auth_state`, `risk_settings` |
| 0004/0005 | `lab_strategies`, `lab_marks`, `option_history`, `entry_book_json`, `pnl_book_unit` |
| 0006/0007 | barras diárias da B3, `cost_settings` |
| 0008 | `portfolio_settings`, `portfolio_fills`, `decision_log` (id = hash do conteúdo; anulação lógica por `voided_at`) |
| 0009 | `jarbas_settings`, `jarbas_conversations`, `jarbas_messages`, `jarbas_usage` |

**Não existe:** tabela de alertas, marcação a mercado da carteira persistida, desfecho das decisões, ledger de custo em moeda, tabela de agentes/tarefas. Padrão para nova migration: somente acréscimo (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN`), JSON em `TEXT`, datas ISO, aplicação manual.

### 1.6 PWA atual

- `public/manifest.webmanifest`: nome, `short_name`, `pt-BR`, `start_url /`, `scope /`, `standalone`, cores, ícones 192/512 e maskable. Falta `shortcuts`, `screenshots`, `id`, `categories`, `orientation`, `display_override`.
- `public/sw.js`: cache `b3-shell-v4`; navegação **network-first** com fallback para o shell; `/assets/` e `/icons/` cache-first; `/api/` e cross-origin nunca cacheados. `SKIP_WAITING`, limpeza de caches antigos e `clients.claim()` ok. **Não é stale-while-revalidate** e não tem evento `push`/`sync`.
- Instalação (`beforeinstallprompt`), banner, persistência da recusa, detecção standalone e fallback iOS: prontos em `src/components/AppStatus.tsx`. Atualização em `src/main.tsx`.
- Offline: aviso por `navigator.onLine`, Jarbas desabilitado offline, `ApiError(0)` sem conexão. **Não há página offline própria**.
- **Push: inexistente** (nenhum `PushManager`, VAPID ou evento `push` no SW; nenhum backend de envio).
- Fontes externas não passam pelo SW. Chunks dinâmicos (`PriceChart`, `price-charts`) não entram no pre-cache, porque o regex lê só `dist/index.html`.
- CSP em `vercel.json` permite SW e manifest; `connect-src 'self'` bloquearia SDK de push externo; não há `media-src` explícito (mídia externa seria bloqueada). `public/` é incluído no deploy.

### 1.7 Hermes e orquestração multiagente

Achado mais importante da auditoria anterior: **o “Hermes” integrado não é um agente autônomo**. Em `app/jarbas/providers.py` ele é registrado como `OpenAICompatibleProvider` usando `/chat/completions`:

- Payload: `model`, `messages`, `temperature`, `max_tokens`. **Não há** `tools`, `tool_choice`, `functions`, execução de código nem criação de subagentes.
- Resposta lida: somente `choices[0].message.content` e `usage.prompt_tokens/completion_tokens`. **Não há** leitura de `tool_calls`.
- `HERMES_BASE_URL`/`JARBAS_HERMES_BASE_URL` (obrigatória), `HERMES_MODEL` ou `JARBAS_HERMES_MODEL` e chave opcional. URL validada contra SSRF (`providers.py:121-146`).
- Provedores preservados: OpenRouter, Gemini, Groq, Hermes e custom; ordem padrão `openrouter → gemini → groq → custom → hermes`, reordenável em `/jarbas/settings`. Cooldowns em memória; não persistentes.
- Consumo: `jarbas_usage` por dia/provedor/modelo; `daily_limit=200` global; limite de 20 requisições/min por instância. **Não há ledger financeiro em R$/US$**.
- Já existem especialistas determinísticos reais em `quant/` (volatilidade, gregas, payoff, risco, structure, lab, open interest) e o par `agents/risk_manager.py` + `agents/orchestrator/supervisor.py`, com barramento **volátil** em `core/bus.py`. A trilha permanente é `decision_log`.
- Não existe validação independente separada da proposta; o que existe é recálculo determinístico em `quant/risk.py` e reprovação pelo RiskManager.

**Implicação:** não é seguro afirmar que o Hermes “orquestra agentes” hoje. Qualquer orquestração precisa ser implementada no servidor, com agentes determinísticos e LLM apenas como planejador/sintetizador de texto validado. Proposta de agente criada pelo modelo deve ficar como `PROPOSTA` e só virar ativa após aprovação do proprietário — nunca por autoexecução.

## 2. Arquitetura proposta

1. **Envelope único de dados de mercado.** Padronizar em todas as respostas de mercado/lab/decisões:
   `{ provenance: {source, kind, collected_at, market_time, delay_seconds}, data_status, quality, missing, label }`, onde `label` é um dos rótulos `REAL`, `HISTÓRICO`, `CALCULADO`, `SIMULADO`, `OBSERVADO`, `INDISPONÍVEL`. Aplicar primeiro a `asset`, `chain`, `strategies`, `calendars`, `scanner` e `lab`.
2. **Contratos versionados.** Declarar `response_model` nas rotas de leitura e gerar tipos TS a partir do contrato; rejeitar `body as T` sem validação no cliente. Separar `GET /assets/{symbol}/strategies` (somente leitura) de um comando explícito que registra decisão.
3. **Serviços de domínio reutilizando o que existe.** Nenhum banco paralelo: estender `db/migrations` com uma nova migration `0010` para agentes/tarefas/alertas/marcação a mercado. Manter `decision_log`, `lab_*`, `jarbas_usage` e o cliente Turso atual.
4. **Orquestrador multiagente no servidor.** Registro estático de agentes (id, papel, módulo determinístico, ferramentas permitidas, orçamento, estado), fila de tarefas persistida, execução assíncrona por cron protegido e painel de aprovação. Hermes/OpenRouter/Gemini/Groq/custom continuam **somente** como provedores de linguagem; nenhum agente recebe shell, escrita de arquivo, chave ou acesso a ordens.
5. **PWA como shell.** Service worker com pre-cache incluindo chunks dinâmicos, página offline própria, splash via manifest + CSS, atualização com confirmação quando houver estado não salvo. Push só após decisão explícita (VAPID + ajuste de CSP + consentimento).
6. **Interface (Google AI Studio).** Shell com sidebar no desktop e navegação inferior no celular, tokens de cor/espacemento já existentes em `src/index.css` expandidos para cards/KPIs, gráficos adaptáveis e menos texto. OpenCode fornece os contratos e valida a integração; não reescreve a identidade Newsprint sem aprovação.

## 3. Fases de entrega

| Fase | Escopo | Responsável | Critério de aceite |
|---|---|---|---|
| 1. Contratos e verdade numérica | Envelope de proveniência/qualidade em todas as respostas de mercado e Lab; `response_model`; separar leitura de comando em estratégias; sincronizar `src/types.ts` | OpenCode | Testes de contrato garantindo que nenhuma resposta de mercado omita `data_status`/`quality`; nenhuma mudança de número calculado |
| 2. Backend dos módulos faltantes | Alertas persistidos com deduplicação e `read_at`; marcação a mercado da carteira (`equity`, PnL aberto, `as_of`); agregado previsto × realizado; rota `/settings` agregada | OpenCode | Testes ponta a ponta com SQLite real; simulado nunca aparece como observado |
| 3. Orquestração e agentes | Migration `0010`, registry de agentes, fila, cron, orçamento, propostas com aprovação, validador independente antes de `TECNICAMENTE VALIDADO` | OpenCode | Testes de permissão/allowlist; nenhuma ferramenta sensível; nenhuma ordem; evidência de execução no banco |
| 4. PWA e shell visual | Manifest completo, SW com chunks dinâmicos e offline page, nav desktop/mobile, design tokens e componentes financeiros | Google AI Studio + OpenCode (integração) | Instalação, offline, atualização e responsividade validados em desktop e celular |
| 5. Validação final | Todas as telas, fluxos operacionais, persistência, gráficos, performance e relatório técnico | Ambos | Suíte completa + E2E dos fluxos críticos + relatório de limitações |

## 4. Decisões que precisam de autorização explícita

1. **Criar a migration `0010`** (nova tabela de agentes/tarefas/alertas/marcações). Não criar banco paralelo.
2. **Adicionar cron agendado** para a fila de agentes. O cron atual é diário; o plano da Vercel pode limitar frequência — confirmar antes de propor execução por minuto.
3. **Notificações push**: exigem VAPID, backend de envio, consentimento e ampliação de `connect-src` no CSP. Hoje não existem; não implementar sem autorização.
4. **Mudança visual estrutural** (sidebar/nav inferior, troca de tokens, nova aba de Payoff, tela de Configurações): depende do artefato do Google AI Studio.
5. **Criação autônoma de agentes pelo LLM**: recomendação do OpenCode é **proibir autoativação**; o modelo pode propor, o proprietário aprova.
6. **Vídeo**: não há base nem infraestrutura; tratar como preparação de interface, não como funcionalidade entregue, salvo decisão em contrário.

## 5. O que não será feito

- Copiar identidade, logotipo, textos ou componentes do InfoMoney.
- Criar dados fictícios, mocks em produção ou “estimativas” apresentadas como cotação real.
- Substituir Turso por outro banco ou duplicar persistência.
- Adicionar envio de ordens, execução financeira automática, shell ou permissão de escrita a agentes.
- Remover funcionalidades validadas (Scanner, Estratégias, Laboratório, Carteira, Jarbas).
- Promover o Hermes a orquestrador sem evidência de capacidade de `tool calling` no endpoint configurado.

## 6. Evidências e acompanhamento

- Relatório de estado visual atual: `docs/status-visual.html`.
- Regras quantitativas: `docs/quant-convencoes.md`, `docs/fontes-de-dados.md`, `docs/laboratorio.md`.
- Estado dos agentes atuais: `docs/agentes-estado.md`.
- Auditoria histórica e decisão de não instalar o Hermes como dependência: `docs/FASE0_AUDITORIA_B3_INTELLIGENCE_CORE.md`.
- Linha de base de validação: 616 testes Python + 81 testes Vitest + lint + build (24/11/2026).

Ao final de cada fase, o relatório deve listar arquivos alterados, testes executados, deployち ID e limitações remanescentes. Nenhuma funcionalidade será considerada concluída apenas pela existência da interface.
