# Plano técnico — Integração definitiva do PWA (Google AI Studio) à plataforma existente

Data: 24/11/2026. Status: **Fases 1 e 2 executadas e validadas localmente; Fases 3 a 5 aguardando autorização**.

Origem do PWA: `C:\Users\wordi\Downloads\b3-opções-pro`
Plataforma de destino: `D:\projetos\b3-opcoes\B3-OPCOES-PRO--main (3)\B3-OPCOES-PRO--main`

## 0. Diagnóstico do estado atual

### 0.1 Git e trabalho em andamento

- Branch: `feature/b3-intelligence-core`, alinhada a `origin/main` em `036a7f9`.
- Não há commit/push/deploy pendente referente ao PWA.
- Alterações locais **não commitadas** encontradas antes desta auditoria:
  - `app/service.py` (modificado) — início da Fase 1 de contratos: envelope de procedência em `asset`, `chain`, `strategies` e `calendars`;
  - `app/contracts.py` (novo) — modelos Pydantic de resposta e helpers do envelope;
  - `docs/plano-redesign-pwa.md` (novo) — plano de redesign anterior.
- Validação rápida do estado parcial: `compileall` OK e `tests/test_api.py` 40/40. A suíte completa ainda não foi rodada após essas alterações.
- **Decisão necessária:** concluir essa Fase 1 como parte da integração, mantê-la congelada ou descartá-la. Não farei reset destrutivo sem autorização explícita.

### 0.2 Origem do PWA (Google AI Studio)

A origem é um **front-end de demonstração visual muito bem estruturado**, não um produto integrável por cópia.

- Stack: React 19.3, Vite 8 (Rolldown), TypeScript 7, Tailwind 4.3, `lightweight-charts` 5.3, `lucide-react`, `vite-plugin-pwa` 2.
- 12 páginas, `AppShell` com sidebar desktop + tabbar mobile, tema dark fixo, fontes Plus Jakarta/DM Sans/JetBrains.
- PWA real no cliente: manifest gerado, Workbox, install prompt, offline banner, update button, ícones e gerador de ícones. **Push não implementado** (apenas `Notification.requestPermission()`).
- Camada de dados: `dataGateway.ts` alterna `production` e `demo`. O modo `demo` vem de `src/data/demoFixtures.ts` (~1.200 linhas) com cotações, candles, agentes, recomendações e mensagens Hermes **fictícias e explicitamente marcadas como demonstração**.
- Backend próprio: **não existe**. Express/dotenv aparecem no `package.json`, mas não há servidor. Nenhum banco próprio e nenhuma chave real no bundle.
- Contratos esperados pelo PWA (`docs/OPENCODE_INTEGRATION_CONTRACTS.md`) não batem com a API atual: `/api/market/dashboard-pulse`, `/api/options/scanner`, `/api/hermes/chat`, `/api/agents`, `/api/monitoring/recommendations`, `/api/market/global`, `/api/fundamentals/rankings`, `/api/media/reports`.
- O contrato `POST /api/options/orders/real-intent` **é incompatível com a regra do produto** (sem ordens/execução financeira). Será rejeitado.
- Funcionalidades com cálculo real no PWA: `optionsMath.ts` (payoff, break-even, lote 100) e `technicalIndicators.ts` (EMA, SMA, Bollinger, RSI, MACD). O gráfico `CandlestickProChart.tsx` usa `lightweight-charts` corretamente.
- Funcionalidades que são **casca/stub**: chat Hermes com respostas por palavra-chave, ações de agentes apenas em memória, aprovações em monitoramento apenas locais, player de mídia simulado com `setInterval`, rankings/histórico/mercados globais sobre fixtures.

### 0.3 Plataforma de destino (projeto real)

- React 19, Vite 6.4, TypeScript 5.8, Tailwind 4.1, `lightweight-charts` 5.2, Recharts 3.8, Vitest 5.1, pytest.
- FastAPI com **39 rotas** `/api`, sessão em cookie `HttpOnly + Secure + SameSite=Strict`, rate limit de login, Turso/SQLite único com migrations `0001`–`0009`.
- Jarbas real: texto, voz pt-BR via Web Speech, histórico persistido, provedores OpenRouter/Gemini/Groq/Hermes/custom, `/api/jarbas/diagnose`.
- Núcleo analítico validado: Scanner, 11 estratégias, payoff, Lab, Carteira, decisões e risk manager. 616 testes Python + 81 Vitest na última linha de base.
- PWA atual: manifest estático, `sw.js` `b3-shell-v4`, instalação, offline e atualização. `/api` nunca é cacheado. CSP `connect-src 'self'` e `worker-src 'self'`.
- Tema próprio `--dp-*` claro/escuro/automático. **Importar o CSS da origem destruiria o theme toggle e a identidade atual.**
- Já existem testes que garantem 404 em rotas de ordens e recusa de `SourceKind.TEST` em produção.

### 0.4 Conflitos críticos

| Conflito | Impacto | Resolução |
|---|---|---|
| Vite 8/TS 7 vs Vite 6/TS 5.8 | `package.json` não pode ser mesclado | Manter o build atual; portar código, não dependências |
| 12 páginas vs 6 abas atuais | Colisão de `App.tsx`, `DashboardPage`/`Dashboard`, etc. | Adaptar páginas como componentes adaptados ao `activeTab`/router leve; substituir direto |
| Temas incompatíveis | Perda do modo claro e dos candles atuais | Traduzir tokens para `--dp-*`; não importar `index.css` da origem |
| Rotas divergentes | PWA não conversa com o backend | Criar adaptador em `src/services/api.ts`; não criar backend paralelo |
| `credentials: 'include'` + origem distinta | Sessão/CSRF | Manter `same-origin`; só considerar CORS se houver decisão explícita |
| `demoFixtures.ts` | Risco de dado fictício em produção | Excluir do build; no máximo manter fora de produção com bandeira explícita |
| Push/VAPID | CSP e backend de envio inexistentes | Não implementar sem autorização |
| Ordem real | Proibido | Remover contrato/botão; nenhuma rota de execução |
| PWA duplicado | Dois SW/manifests | Fundir em um manifest e um SW |

## 1. Arquitetura de integração adotada

Uma aplicação, um backend, um banco, um Jarbas. Web e PWA são **a mesma SPA**, com layouts adaptados por largura de tela.

- `src/services/api.ts` continua sendo o **único dataGateway**. As rotas do PWA externo serão mapeadas para as rotas reais do FastAPI.
- `app/contracts.py` + `response_model` padronizam `{ provenance, data_status, quality, missing, label }` sem quebrar chaves legadas.
- `src/types.ts` espelha esses contratos. Nenhum `body as T` sem pelo menos validação do envelope nas rotas de mercado/lab.
- Jarbas continua no backend; o PWA consome `/api/jarbas/*`. Nenhuma chave `VITE_*` com segredo.
- Turso continua no `db/client.py`; nenhuma migration paralela. `0010` só se aprovado o módulo de agentes/alertas.
- O shell visual do PWA (sidebar + bottom nav + cards) é portado para dentro do tema `--dp-*`. Componentes com lógica própria são adaptados aos tipos/API atuais.
- `public/manifest.webmanifest` e `public/sw.js` continuarão sendo os únicos arquivos de PWA; serão ampliados, não duplicados.

### 1.1 Mapa de rotas do PWA → API real

| Rota esperada pelo PWA | Destino real | Ação |
|---|---|---|
| `/api/market/dashboard-pulse` | composição de `/api/scanner` + `/api/assets/{symbol}` + `/api/watchlist` | Adaptador no front; sem novo endpoint |
| `/api/options/scanner` | `GET /api/scanner` | Renomear chamada no adaptador |
| `/api/options/templates` | usar estruturas já implementadas em `StrategyView`/`strategies` | Evitar endpoint duplicado |
| `/api/market/candles?symbol=` | `GET /api/assets/{symbol}` → `history` | Reaproveitar candles existentes |
| `/api/hermes/workspace` | `/api/jarbas/conversations` + `/api/jarbas/status` | Adaptar |
| `/api/hermes/chat` | `POST /api/jarbas/chat` | Adaptar; manter contexto real |
| `/api/agents` | não existe | Somente após migration `0010`/fila; até lá painel oculto ou `INDISPONÍVEL` |
| `/api/monitoring/recommendations` | `/api/lab/opportunities`, `/api/lab/strategies`, `/api/decisions` | Compose no adaptador |
| `/api/market/global` | não existe | Não inventar: mostrar `INDISPONÍVEL` ou ocultar até fonte autorizada |
| `/api/fundamentals/rankings` | não existe | Não inventar: mostrar `INDISPONÍVEL` |
| `/api/media/reports` | não existe | Preparação visual; sem player falso |
| `/api/options/orders/real-intent` | — | **Rejeitado** |

## 2. Fases de execução

### Fase 1 — Contratos e preservação (pré-requisito)

Concluir o trabalho já iniciado:

1. Finalizar o envelope em `scanner`, `expirations`, `lab` e `decisions`.
2. Declarar `response_model` nas rotas de leitura sem descartar chaves legadas (`extra="allow"`).
3. Separar `GET /assets/{symbol}/strategies` de um `POST` explícito de registro de decisões; ligar o POST a uma ação do usuário.
4. Sincronizar `src/types.ts` e validar o envelope no cliente para rotas de mercado/lab.
5. Rodar suíte completa antes de qualquer integração visual.

**Critério de aceite:** nenhuma resposta de mercado/lab sem envelope; nenhuma mudança de número calculado; GET de estratégias sem gravar `decision_log`.

### Fase 2 — Shell e componentes adaptados

1. Portar o padrão de `AppShell`: sidebar desktop, bottom nav mobile, drawer “Todos os módulos”.
2. Portar cards/KPIs e hierarquia visual, traduzindo tokens para `--dp-*`.
3. Adaptar `CandlestickProChart`/indicadores `technicalIndicators.ts` apenas se agregarem algo sobre `PriceChart.tsx`/`HvChart`; evitar duplicação.
4. Manter Jarbas, Lab, Carteira e Scanner com os componentes/dados atuais; trocar só a apresentação.
5. Esconder ou marcar como `INDISPONÍVEL` módulos sem backend real (mercados globais, fundamentalistas, mídia, agentes autônomos).

**Critério de aceite:** mesmas funcionalidades em desktop e mobile; nenhum fixture no build de produção; navegação e login preservados.

### Fase 3 — PWA unificado

1. Ampliar `manifest.webmanifest`: `id`, `shortcuts`, `categories`, `display_override`, screenshots quando houver.
2. Atualizar `public/sw.js`: pre-cache dos chunks dinâmicos (`PriceChart`, `price-charts`), página offline própria, bump de versão, limpeza de cache antigo, `SKIP_WAITING`.
3. Manter `/api` fora de qualquer cache; nenhuma cotação antiga servida como atual.
4. Fundir install/update/offline do PWA externo com `AppStatus.tsx` — um único fluxo.
5. Push/VAPID continua bloqueado até autorização e ajuste de CSP.

**Critério de aceite:** uma instalação, um SW, um manifest, offline sem dado falso, update controlado.

### Fase 4 — Agentes e inteligência (opcional, separada)

Somente com autorização explícita: migration `0010`, registry/fila no servidor, cron, propostas `PROPOSTA` até aprovação, validador independente antes de `TECNICAMENTE VALIDADO`. Hermes continua provedor de linguagem; não vira orquestrador autônomo sem evidência de `tool calling`.

### Fase 5 — Validação e entrega

1. Web: login, dashboard, navegação, scanner, estratégias, payoff, Lab, Carteira, Jarbas, persistência.
2. PWA: instalação, standalone, login, navegação inferior, Jarbas, offline, update, reconexão.
3. Automatizado: pytest + Vitest + lint + build. Dispositivos reais: Android/iOS separadamente, com evidência prática.
4. Git: `git status`, diff revisado, commit somente após validação, push/deploy **somente com autorização**.
5. Relatório final: arquivos, testes automatizados, validações locais, validações em dispositivo, deploy, limitações.

## 3. Autorizações necessárias

1. Concluir ou descartar as alterações da Fase 1 já em andamento.
2. Portar o shell visual do PWA externo para dentro do tema atual.
3. Ampliar manifest/SW e criar página offline.
4. Migration `0010`, cron de agentes e fila persistida — se Fase 4 for incluída.
5. Push/VAPID e mudança de CSP — separadamente.
6. Commit, push e deploy — separadamente, com evidência.

## 4. O que não será feito

- Copiar o projeto PWA por cima do frontend atual.
- Importar `demoFixtures.ts`, mocks, valores fixos ou respostas “canned” como dados reais.
- Criar segundo backend, segundo banco, segundo Jarbas, segundo service worker ou segundo manifest.
- Adicionar execução de ordens, boleta, webhook de corretora ou autoexecução.
- Introduzir segredos em variáveis `VITE_*` ou chaves de IA no navegador.
- Importar dependências incompatíveis (Vite 8, TS 7) ou sobrescrever tokens `--dp-*`.
- Declarar integração concluída sem testes e sem validação em dispositivo quando prometido.

## 4.1 Registro de execução (24/11/2026)

- Fase 1 concluída: envelope em `asset`, `chain`, `strategies`, `calendars`, `scanner`, `expirations`, `decisions`, Lab (oportunidades, lista, detalhe e ranking); `response_model` com `extra="allow"`; `GET /assets/{symbol}/strategies` passou a ser somente leitura e `POST /assets/{symbol}/strategies/decisions` registra decisões sob comando explícito.
- Fase 2 concluída: `src/components/AppShell.tsx` (sidebar desktop, barra inferior e drawer mobile), `Masthead.tsx` compacto e `App.tsx` usando o shell único; `StrategyView.tsx` ganhou botão “Registrar decisões”. Nenhum `demoFixtures.ts`, tema dark externo, Vite 8/TS 7, segundo backend ou segundo PWA foi importado.
- Validação local: `pytest` 617/617, Vitest 87/87, `tsc --noEmit` limpo, `vite build` OK, preview local com HTTP 200 para HTML, manifest e service worker. Nenhuma validação em dispositivo Android/iOS foi executada.
- Git: alterações permanecem não commitadas; push e deploy não foram executados.

## 5. Evidências de partida

- Origem PWA: `docs/OPENCODE_INTEGRATION_CONTRACTS.md`, `src/data/demoFixtures.ts`, `src/services/dataGateway.ts`, `vite.config.ts`.
- Plataforma atual: `app/main.py` (39 rotas), `db/migrations/0001`–`0009`, `src/services/api.ts`, `src/index.css`, `public/sw.js`, `vercel.json`.
- Linha de base de testes: 616 Python + 81 Vitest; estado parcial atual: 40 testes de `test_api.py` passaram após o início da Fase 1.
