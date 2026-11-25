# B3 Opções Pro — Relatório de Auditoria Final e Preparação para Homologação PWA

**Data:** 2026-11-24  
**Responsável pelo projeto:** Joel Oliveira  
**Arquiteto e orientador técnico:** Jarbas (ChatGPT)  
**Agente executor:** OpenCode  
**Escopo:** auditoria independente, somente leitura, das Fases 1 e 2 consolidadas; reexecução de testes; smoke local; preparação de checklist para Android e iPhone.  
**Status geral:** **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL.** A homologação **não** foi declarada.

Classificações utilizadas: **APROVADO**, **REPROVADO**, **NÃO EXECUTADO**, **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL**.

---

## 1. Resumo executivo

| Item | Resultado | Classificação |
|---|---|---|
| Diretórios confirmados antes de qualquer comando | Origem do PWA e repositório integrado identificados separadamente | **APROVADO** |
| Preservação do repositório | Nenhum arquivo de código alterado; alterações pré-existentes mantidas | **APROVADO** |
| Arquitetura aprovada | Uma SPA, um FastAPI, um Turso, um Jarbas, um gateway, uma sessão, um manifest, um SW | **APROVADO** (estático) |
| Backend | `pytest -q`: 617 aprovados, 1 aviso, 113,87 s | **APROVADO** |
| Frontend — lint | `npm run lint` (`tsc --noEmit`): saída sem erros | **APROVADO** |
| Frontend — testes | `npm test -- --run`: 9 arquivos, 87 testes aprovados, 11,31 s | **APROVADO** |
| Frontend — build | `npm run build`: 2356 módulos, build concluído em 6,79 s | **APROVADO** |
| Smoke de produção local | `/`, `/manifest.webmanifest` e `/sw.js` com HTTP 200 | **APROVADO** |
| Bundle | Ausência de fixtures, contratos financeiros, chaves privadas e valores de segredos | **APROVADO** com ressalvas (itens 15 e 13) |
| Android | Sem acesso a dispositivo físico | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| iPhone | Sem acesso a dispositivo físico | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| Fase 3 / Fase 4 | Não implementadas nesta rodada | **NÃO EXECUTADO** |
| Commit, push, deploy, migrations, cron, operações financeiras | Não executados | **NÃO EXECUTADO** |

**Conclusão:** a base técnica das Fases 1 e 2 está consistente e os testes automatizados reexecutados passaram. Contudo, a homologação depende de execução em Android e iPhone, verificação de runtime em produção e decisão de Joel sobre os problemas listados na seção 15. Nenhuma liberação foi concedida nesta auditoria.

---

## 2. Diretórios e repositórios inspecionados

| Finalidade | Caminho confirmado | Uso nesta auditoria | Classificação |
|---|---|---|---|
| Origem do PWA (Google AI Studio) | `C:\Users\wordi\Downloads\b3-opções-pro` | Confirmado. Contém `docs`, `public`, `scripts`, `src`, `.env.example`, `package.json`, `vite.config.ts`, etc. **Não é o repositório principal.** Não foi modificado. | **APROVADO** |
| Plataforma integrada (repositório real) | `D:\projetos\b3-opcoes\B3-OPCOES-PRO--main (3)\B3-OPCOES-PRO--main` | Todos os comandos Git, testes, build e leituras foram executados aqui. | **APROVADO** |
| Outros diretórios do workspace | `backup-*`, `copia-trabalho-2026-11-03`, arquivos de auditoria/pasta de senha | Observados, **não** usados como base de execução; credenciais não foram abertas. | **NÃO EXECUTADO** |

O diretório de origem e o repositório integrado foram tratados como projetos distintos, conforme exigido.

---

## 3. Arquitetura encontrada

| Elemento | Evidência | Classificação |
|---|---|---|
| SPA única | `src/main.tsx`, `src/App.tsx`; `App` renderiza `Login` ou `Workspace` (`src/App.tsx:49-50`) | **APROVADO** |
| Backend FastAPI único | `app/main.py:192-193` (`docs_url=None`, `redoc_url=None`, `openapi_url=None`), `router = APIRouter(prefix="/api")` em `app/main.py:193`; Vercel reescreve `/api/:path*` para `/api/index` (`vercel.json:5-10`) | **APROVADO** |
| Banco Turso único | `db/client.py`; migrations `0001` a `0009` presentes; **nenhuma `0010`** | **APROVADO** |
| Jarbas único | `app/jarbas/*`; `POST /api/jarbas/chat` em `app/main.py:604`; histórico em `jarbas_conversations`/`jarbas_messages` | **APROVADO** |
| Gateway único | `src/services/api.ts`; `credentials: 'same-origin'` (`:51`), `readEnvelope` (`:77`), `checked` (`:103-104`) | **APROVADO** |
| Sessão única | cookie `b3_session`, `httponly=True`, `secure=not config.insecure_cookie`, `samesite="strict"` (`app/main.py:270-272`) | **APROVADO** com ressalva (item P3) |
| Manifest único | `public/manifest.webmanifest`, referenciado em `index.html:9` | **APROVADO** |
| Service worker único | `public/sw.js`, identificador `b3-shell-v4` (`sw.js:8`) | **APROVADO** |
| Cron pré-existente | `vercel.json:66-70` agenda `/api/cron/scan`; rota em `app/main.py:365` com `CRON_SECRET` (`app/main.py:49,60`). **Não executado nesta auditoria.** | **NÃO EXECUTADO** |
| Aplicações paralelas, bancos extras, gateways duplicados | Não encontrados na varredura estática | **APROVADO** |
| Estado real em produção/Turso/env | Não verificado | **NÃO EXECUTADO** |

**Observação sobre contagem de rotas:** o código atual contém **40** decorators `@router.*` (24 GET, 10 POST, 4 PUT, 2 DELETE), não 39. A diferença é compatível com a rota `POST /assets/{symbol}/strategies/decisions` acrescentada na Fase 1 (`app/main.py:492`). Documentação antiga que cita 39 rotas está desatualizada (item P16).

---

## 4. Auditoria frontend

### APROVADO

- As seis abas implementadas em `src/App.tsx:87-104` correspondem a `NAV_ITEMS` em `src/components/AppShell.tsx:19`.
- Desktop usa sidebar fixa em `lg` (`AppShell.tsx:55`, container com `lg:pl-64` em `:98`); mobile usa bottom nav (`AppShell.tsx:111-112`, `lg:hidden`) e drawer (`AppShell.tsx:153-177`).
- Navegação não expõe módulos sem backend (global, rankings, mídia, agentes ou ordens) como abas funcionais.
- Gateway único: não foram encontrados `fetch(` Diretos em componentes fora de `src/services/api.ts`; todas as chamadas usam `/api` com `credentials: 'same-origin'` (`api.ts:49-51`).
- 401 tratado centralmente (`api.ts:59`) com callback de unauthorized (`src/App.tsx:34`).
- Envelope validado no cliente: `readEnvelope` (`api.ts:77`) e `checked` (`api.ts:103-104`).
- Registro de decisões é ação explícita: comentário e função em `api.ts:261-266` chamam `POST /assets/{symbol}/strategies/decisions`.
- Tema claro/escuro preservado por tokens `--dp-*` (`AppShell.tsx:4`, `src/index.css:8,57,80`); `lib/tema.ts` mantém `claro`, `escuro` e `automatico`.
- Nenhum `import` de `demoFixtures` ou gateway de demonstração em `src` (varredura direta).

### REPROVADO — divergências confirmadas no código

| ID | Achado | Evidência | Impacto |
|---|---|---|---|
| P4 | Drawer com `aria-modal="true"` sem focus trap, sem fechar com `Escape` e sem retorno de foco | `AppShell.tsx:153-165`; varredura de `Escape`/`focus()`/`useRef` no arquivo: sem correspondências | Navegação por teclado/leitor de tela pode ficar presa ou sem contexto |
| P5 | Painel do Jarbas sem foco inicial e sem `Escape` para sair | `src/components/Jarbas.tsx`; varredura de `Escape`/`focus()`/`autoFocus`: sem correspondências | Acessibilidade reduzida em mobile e teclado |
| P6 | `aria-label` aplicado a elemento genérico (`span`) | `AppShell.tsx:87` | Leitor de tela pode ignorar o rótulo |
| P7 | Bottom nav não usa `env(safe-area-inset-bottom)` | `AppShell.tsx:111-112` usa `pb-24` fixo; `env(safe-area-inset-bottom)` aparece apenas em `Jarbas.tsx:197,219` | Risco de sobreposição pela home indicator no iPhone |
| P8 | Breakpoints divergentes: CSS `@media (max-width:1100px)` e `700px` (`src/index.css:263,273`) vs Tailwind `lg` (1024px) e `md` (768px) | `src/index.css:263,273`; `AppShell.tsx:55,112` | Layout inconsistente em larguras intermediárias |
| P9 | Erro de `/jarbas/status` mascarado como “sem provedor de IA” | `Jarbas.tsx:458` | Dificulta diagnóstico de falha de rede/5xx |
| P10 | Não há UI para voltar ao tema `automatico` | `ThemeToggle.tsx:5-24` alterna apenas `claro`/`escuro`; `lib/tema.ts:14` oferece `Automático` | Usuário que escolhe manualmente não retorna ao modo sistema |
| P18 | Convite de instalação só aparece após login | `InstallPrompt` em `AppStatus.tsx:27-79`, renderizado dentro de `Workspace` via `App.tsx:79`, enquanto `Login` retorna antes (`App.tsx:49`) | Oportunidade de instalação perdida no primeiro acesso |
| P19 | “Ir para o Jarbas” apenas faz scroll, não muda a aba ativa | `AppShell.tsx:47-49`; `Masthead.tsx:25` chama `onOpenJarbas` | Usuário pode não perceber navegação para o Jarbas |
| P20 | Dois abridores do mesmo drawer | `Masthead.tsx:16` (`onOpenMenu`) e `AppShell.tsx:140-141` | Duplicidade de affordance; não é crime arquitetural, mas merece revisão |
| P21 | Possível contraste baixo em texto que usa cor de régua | `--dp-color-rule: #9b978e` (`index.css:8`, tema claro); não foi medido com calculadora de contraste | Legibilidade reduzida; medição formal pendente |

### NÃO EXECUTADO

- Validação visual em navegador real.
- Navegação por teclado e leitor de tela.
- Teste de toque, scroll, teclado virtual e rotação em dispositivo.
- Medição automatizada de contraste (WCAG).

---

## 5. Auditoria backend

### APROVADO

- `app/main.py:481-490`: `GET /assets/{symbol}/strategies` é somente leitura; comentário explicita que decisões não são efeito colateral. `reviewed_strategies` (`main.py:467-479`) apenas lê capital/custos e aplica revisão em memória.
- `app/main.py:492-502`: `POST /assets/{symbol}/strategies/decisions` chama `carteira.record_decisions` (`app/carteira.py:179,193`).
- Teste Python correspondente em `tests/test_carteira.py` (GET sem gravação e POST deduplicado) passou na reexecução.
- Cookie `b3_session` com `HttpOnly`, `Secure` e `SameSite=Strict` (`main.py:270-272`).
- Rate limit de login com limpeza/registro em `app/auth.py:98-111`.
- Envelope aplicado em `app/contracts.py:43-47` (`provenance`, `data_status`, `quality`, `missing`, `label`) e `add_envelope` (`:162-178`); `extra="allow"` em `:20` preserva chaves já consumidas pelo front.
- `pytest -q`: 617 aprovados, 1 aviso (depreciação de `httpx` no `starlette.testclient`), sem falhas.

### REPROVADO

| ID | Achado | Evidência | Impacto | Solução sugerida |
|---|---|---|---|---|
| P1 | `label_from_status()` prioriza `measured` antes de `INDISPONIVEL` | `app/contracts.py:150-159`: `if measured in ("SIMULADO","OBSERVADO"): return measured` vem antes de `if status == "INDISPONIVEL"` | Dado indisponível pode ser rotulado como `SIMULADO`/`OBSERVADO`, induzindo interpretação errada | Verificar `INDISPONIVEL` primeiro; cobrir com teste de prioridade |
| P2 | `Provenance.delay_seconds` declarado, mas nunca preenchido | `app/contracts.py:28`; varredura de `delay_seconds =` em `app/`: apenas a declaração | Envelope always `null` no campo de atraso, enfraquecendo procedência | Calcular a partir de `collected_at`/`market_time` ou remover campo até ser suportado |
| P3 | `B3_INSECURE_COOKIE=1` desliga `Secure` sem guarda de ambiente | `app/main.py:59` e `:271` | Se a variável for definida em produção, cookie sensível trafega sem `Secure` | Permitir apenas quando `ENVIRONMENT`/`VERCEL_ENV` indicar desenvolvimento/teste |
| P16 | Documentação anterior desatualizada (39 rotas; Fases 1/2 não refletidas) | Contagem real: 40 decorators; `docs/plano-integracao-pwa.md` descreve o plano, não o estado final | Auditorias futuras podem usar premissa errada | Atualizar documentação após autorização, sem alterar código agora |

### NÃO EXECUTADO

- Verificação de env vars reais, valores de `CRON_SECRET`, `B3_INSECURE_COOKIE` e segredos de provedores em produção.
- Chamadas reais a provedores de IA.
- Estado de deploy, headers em runtime e conexão Turso real.

---

## 6. Auditoria Turso

### APROVADO

- Migrations presentes: `0001_inicial.sql`, `0002_iv_history.sql`, `0003_seguranca_e_risco.sql`, `0004_laboratorio.sql`, `0005_livro_de_ofertas.sql`, `0006_barras_b3.sql`, `0007_custos.sql`, `0008_carteira.sql`, `0009_jarbas.sql`. Nenhuma `0010`.
- `decision_log` escrito somente no comando explícito: `carteira.record_decisions` (`app/carteira.py:179,193`), chamado por `POST /assets/{symbol}/strategies/decisions` (`main.py:492-502`).
- Tabelas do Jarbas criadas em `0009_jarbas.sql`; persistência em `app/jarbas/store.py:69-106`.
- Nenhuma migration executada nesta auditoria; nenhum registro alterado.

### REPROVADO / esclarecimento necessário

| ID | Achado | Evidência | Impacto | Solução sugerida |
|---|---|---|---|---|
| P17 | A afirmação “GET não grava” é válida para `decision_log`, mas não para todo efeito de escrita | Escritas em leituras/manutenção: `auth.py:98-111` (login failures), `app/cache.py:139`, `app/main.py:388` (limpeza de cache), `app/lab.py:553-562`, `jarbas/store.py:71` | Pode gerar interpretação incorreta de que nenhuma rota GET tem efeito colateral | Documentar o escopo exato da garantia: “GET não registra decisões nem dados financeiros de cliente” |

### NÃO EXECUTADO

- Consulta ao banco real, contagem de linhas, validade de credenciais e aplicação de migrations em produção.

---

## 7. Auditoria Jarbas

### APROVADO

- Rota real: `POST /api/jarbas/chat` (`app/main.py:604`).
- Continuidade: `ensure_conversation`/`history_for_model`/`add_message` (`main.py:621-623`; `store.py:69-106,124-143`).
- System prompt em português brasileiro: `app/jarbas/assistant.py:60` (“Fale em português do Brasil...”).
- Voz no front: `Jarbas.tsx:6` (`../lib/voice`), síntese em `:144`, botão em `:240`, seleção de voz e velocidade em `:538-559`.
- Provedores apenas no backend: `app/jarbas/providers.py:359-397` (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `HERMES_BASE_URL`). Nenhuma chave em `VITE_*` no `src`.
- Não há evidência de `tool calling` nativo: `app/jarbas/tools.py:180` (`gather`) injeta contexto no prompt; não foram encontrados `tool_calls`/`function_call`. Portanto, Hermes continua sendo provedor de linguagem, não orquestrador autônomo.

### REPROVADO

| ID | Achado | Evidência | Impacto | Solução sugerida |
|---|---|---|---|---|
| P9 | Falha de status é apresentada como ausência de provedor | `Jarbas.tsx:458` | Erro de rede/5xx pode ser confundido com configuração | Diferenciar `error.status`, `network error` e `configured.length === 0` |

### NÃO EXECUTADO

- Chamada real a provedor remoto, qualidade da resposta, continuidade em sessão real e voz em Safari/iOS.
- Persistência verificada em Turso de produção.

---

## 8. Auditoria PWA

### APROVADO

- Manifest: `public/manifest.webmanifest:2-10` com `name`, `short_name`, `lang pt-BR`, `start_url "/"`, `scope "/"`, `display "standalone"`; ícones 192/512 e maskable em `:11-15`. `index.html:9-14` referencia manifest, ícone, apple-touch-icon e `mobile-web-app-capable`.
- Service worker: identificador `b3-shell-v4` (`public/sw.js:8`); navegação network-first (`:38-47`); assets cache-first (`:49-58`); `/api/` fora de cache (`:63`); `SKIP_WAITING` (`:24-26`); aviso `b3-update-ready` consumido em `AppStatus.tsx:92,108-113`.
- Comentário explícito de que cotações e respostas de IA não são cacheadas (`sw.js:2-4`).
- Fonte única de instalação: `InstallPrompt` em `AppStatus.tsx:27-79` (comportamento nativo no Android e instrução no iPhone).

### REPROVADO

| ID | Achado | Evidência | Impacto | Solução sugerida (Fase 3, mediante autorização) |
|---|---|---|---|---|
| P11 | Falta `apple-mobile-web-app-capable` | `index.html:12-14` tem `mobile-web-app-capable`, `apple-mobile-web-app-title` e status bar, mas não a meta Apple de capability | iOS pode não abrir em standalone conforme esperado | Adicionar meta específica quando Fase 3 for autorizada |
| P12 | Manifest carece de `id`, `shortcuts`, `categories`, `display_override`, `screenshots`, `orientation` | Arquivo termina na linha 16 | Limitações de instalação/apresentação | Ampliar manifest na Fase 3 |
| P13 | Chunks dinâmicos não entram no pre-cache | `sw.js:9` lista só HTML/manifest/ícones; `:17-19` descobre assets a partir do HTML gerado. Build gera `PriceChart-*.js` e `price-charts-*.js` | Primeiro acesso offline a gráficos pode falhar | Incluir chunks no pre-cache ou aquecer routes na Fase 3 |
| P14 | `activate` apaga **todos** os caches da origem | `sw.js:31-32`: `caches.keys()` filtra apenas quem não é `CACHE` | Pode apagar caches de outras aplicações na mesma origem | Filtrar por prefixo `b3-` |
| P15 | Não há refetch automático ao reconectar | `AppStatus.tsx:87-107` só alterna aviso `online`/`offline`; SW é network-first apenas em navegação (`sw.js:66-67`) | Dados podem permanecer desatualizados até recarregar | Disparar `reload()` das resources ao voltar `online` |
| P18 | Convite de instalação depende de login | `AppStatus.tsx` dentro de `Workspace` (`App.tsx:79`); `Login` retorna antes (`App.tsx:49`) | Perde-se o momento de instalação no primeiro acesso | Avaliar exibição fora da área autenticada |
| P22 | Safe-zone do ícone maskable não foi inspecionada visualmente | Arquivo existe, mas ferramenta não avaliou imagem | Risco de corte em launcher Android | Validar em dispositivo |

### NÃO EXECUTADO

- Instalação real, execução standalone, offline real, reconexão e atualização em dispositivo.
- Push/VAPID, nova página offline, novos chunks, alterações de CSP e ampliação do manifest — todos pertencem à **Fase 3** e não foram implementados.

---

## 9. Testes executados

| Comando | Resultado | Classificação |
|---|---|---|
| `& '.venv/Scripts/python' -m pytest -q` | `617 passed, 1 warning in 113.87s (0:01:53)` | **APROVADO** |
| `npm run lint` | `> tsc --noEmit`, sem saída de erro | **APROVADO** |
| `npm test -- --run` | `Test Files 9 passed (9)`, `Tests 87 passed (87)`, `Duration 11.31s` | **APROVADO** |
| `npm run build` | `✓ 2356 modules transformed`, `✓ built in 6.79s` | **APROVADO** |
| Smoke local (`python -m http.server 4173 --bind 127.0.0.1 --directory dist`) | `/`, `/manifest.webmanifest`, `/sw.js` → HTTP 200 | **APROVADO** |
| Varredura do `dist` | Ver seção 13 | **APROVADO** com ressalvas |
| Testes em Android/iPhone | Sem dispositivo | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| Deploy / migrations / cron / operações financeiras | Não executados | **NÃO EXECUTADO** |

**Falhas:** nenhuma. **Aviso:** apenas `StarletteDeprecationWarning` sobre `httpx` no `starlette.testclient`, sem impacto funcional nos testes executados.

---

## 10. Evidências dos testes

### Git inicial (antes de qualquer ação)

```text
## feature/b3-intelligence-core...origin/main
 M app/lab.py
 M app/main.py
 M app/service.py
 M src/App.tsx
 M src/app.test.tsx
 M src/components/Masthead.tsx
 M src/components/StrategyView.tsx
 M src/services/api.ts
 M src/types.ts
 M tests/test_carteira.py
?? app/contracts.py
?? docs/plano-integracao-pwa.md
?? docs/plano-redesign-pwa.md
?? src/components/AppShell.tsx
?? src/envelope.test.tsx
?? src/shell.test.tsx
HEAD                 036a7f9ec32139d925f9675dfe7ab4cd1af14af4
origin/main          036a7f9ec32139d925f9675dfe7ab4cd1af14af4
HEAD...origin/main   0  0
git diff --stat      10 arquivos rastreados, 486 inserções, 169 remoções
git diff --check     sem erros; avisos LF→CRLF em Masthead.tsx, StrategyView.tsx, test_carteira.py
```

### Python

```text
........................................................................ [ 11%]
...
.........................................                                [100%]
617 passed, 1 warning in 113.87s (0:01:53)
```

### Vitest

```text
RUN  v5.1.0 D:/projetos/b3-opcoes/B3-OPCOES-PRO--main (3)/B3-OPCOES-PRO--main
Test Files  9 passed (9)
Tests  87 passed (87)
Duration  11.31s
```

### Build — artefatos gerados

```text
dist/index.html                     1.23 kB  │ gzip:   0.55 kB
dist/assets/index-B2RdVZh_.css      28.72 kB │ gzip:   6.41 kB
dist/assets/PriceChart-L_XlbRWa.js   3.83 kB │ gzip:   1.86 kB
dist/assets/icons-B2B3dsAA.js       11.04 kB │ gzip:   2.89 kB
dist/assets/index-DNazkPDe.js      169.36 kB │ gzip:  48.87 kB
dist/assets/price-charts-BlhZ1l_0.js 180.31 kB │ gzip: 58.39 kB
dist/assets/react-vendor-S9Y3xaM9.js 194.37 kB │ gzip: 60.76 kB
dist/assets/charts-Bf12l9Pj.js      379.60 kB │ gzip: 111.37 kB
```

### Smoke local

```text
/                    => HTTP 200 | text/html                | bytes=1225
/manifest.webmanifest => HTTP 200 | application/manifest+json | bytes=608
/sw.js               => HTTP 200 | text/javascript          | bytes=2518
```

O servidor temporário foi encerrado ao final da coleta.

### Varredura do bundle

- Padrões restritos `(?<![a-z])sk-[A-Za-z0-9_-]{20,} | AIza… | gsk_… | libsql:// | -----BEGIN | real-intent | orders/ | webhook | boleta | demoFixtures`: **nenhuma correspondência**.
- `sk-image-linear-*` encontrado na varredura ampla são **falsos positivos** de nomes de utilitários CSS (`mask-image-linear-*`), não chaves de API.
- Foram encontrados apenas: nomes de variáveis de servidor em mensagem de erro do Jarbas (`Jarbas.tsx:458`) e o texto “Parar demonstração” (`StrategyGuide.tsx:53`), que é um tour visual sobre dados reais de montagem, não `demoFixtures`.

**Não foram coletadas** capturas de tela, gravações, logs de dispositivo nem evidências de runtime em produção.

---

## 11. Checklist Android

Todos os itens abaixo estão **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** — nenhum foi executado nesta auditoria.

| # | Item | Procedimento sugerido | Classificação |
|---:|---|---|---|
| A1 | Abrir no navegador | Chrome Android → URL publicada; conferir carregamento e HTTPS | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A2 | Instalar PWA | Menu → “Instalar app” ou banner; conferir ícone na tela inicial | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A3 | Executar standalone | Abrir pelo ícone; conferir ausência de barra de URL e `display-mode: standalone` | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A4 | Login | Credenciais reais; cookie `b3_session`; retorno após 401 | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A5 | Navegação inferior | Alternar dashboard → estratégias → lab → carteira → scanner; drawer “Todos os módulos” | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A6 | Dashboard | Carregar scanner, alertas e gráficos; conferir envelope/labels | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A7 | Lab | Abrir oportunidades, estratégias, ranking e detalhe | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A8 | Carteira | Visualizar posições; registrar decisão explicitamente; confirmar deduplicação | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A9 | Scanner | Rodar scan e validar estados de carregamento/erro | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A10 | Jarbas | Enviar pergunta, receber resposta em pt-BR, conferir contexto | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A11 | Histórico do Jarbas | Enviar nova pergunta na mesma conversa e recuperar conversas anteriores | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A12 | Voz | Ativar áudio, escutar resposta e usar entrada de voz se disponível | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A13 | Perda de conexão | Ativar modo avião; conferir aviso e ausência de cotações “frescas” enganosas | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A14 | Reconexão | Desativar modo avião; conferir atualização dos dados sem intervenção (ver P15) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A15 | Atualização | Publicar nova versão; conferir aviso “Nova versão” e botão “Atualizar agora” | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A16 | Teclado/leitor de tela | Abrir drawer e Jarbas; testar `Escape`, foco e retorno de foco (P4/P5) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| A17 | Safe-zone / maskable | Conferir recorte do ícone e navegação inferior em aparelho com recorte | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |

---

## 12. Checklist iPhone

Todos os itens abaixo estão **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** — nenhum foi executado nesta auditoria.

| # | Item | Procedimento sugerido | Classificação |
|---:|---|---|---|
| I1 | Abrir no Safari | URL publicada em Safari iOS; conferir carregamento e aviso de instalação | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I2 | Adicionar à tela inicial | Compartilhar → “Adicionar à Tela de Início”; conferir ícone apple-touch | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I3 | Executar standalone | Abrir pelo ícone; conferir status bar, ausência de Safari UI e efeito de `apple-mobile-web-app-capable` (P11) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I4 | Login e sessão | Login real; sessão preservada ao fechar/reabrir; logout | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I5 | Navegação | Bottom nav, drawer e scroll com home indicator (P7) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I6 | Dashboard | Scanner, alertas, gráficos e labels de procedência | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I7 | Lab | Listas, filtros e detalhe de estratégia | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I8 | Carteira | Leitura e registro explícito de decisões | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I9 | Scanner | Execução e estados de erro | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I10 | Jarbas e voz | Chat, resposta em pt-BR, síntese de voz e seleção de voz (`speechSynthesis`) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I11 | Histórico | Continuidade da conversa e recuperação de conversas | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I12 | Offline | Modo avião; conferir aviso e comportamento do shell | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I13 | Reconexão | Voltar online; verificar refetch (P15) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I14 | Atualização | Nova versão publicada; fluxo `b3-update-ready` → `SKIP_WAITING` | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I15 | Tema automático | Alternar claro/escuro e verificar se há volta ao automático (P10) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| I16 | VoiceOver | Drawer e Jarbas com leitor de tela (P4/P5) | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |

---

## 13. Auditoria de segurança

| Verificação | Evidência | Classificação |
|---|---|---|
| Valores de segredos no bundle | Varredura restrita sem correspondência; `sk-*` amplo são falsos positivos CSS | **APROVADO** |
| `demoFixtures`, `real-intent`, `orders/`, `webhook`, `boleta`, `libsql://`, `-----BEGIN` | Nenhuma correspondência no `dist` | **APROVADO** |
| Chaves de IA em `VITE_*` | Nenhuma ocorrência em `src`; provedores apenas em `app/jarbas/providers.py:359-397` | **APROVADO** |
| CSP | `vercel.json:23`: `default-src 'self'`, `script-src 'self'`, `connect-src 'self'`, `worker-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`; `style-src` permite `'unsafe-inline'` e Google Fonts | **APROVADO** com observação |
| Headers adicionais | `nosniff`, `X-Frame-Options DENY`, `Referrer-Policy`, `Permissions-Policy` (`vercel.json:25-40`) | **APROVADO** |
| Cookie de sessão | `HttpOnly`, `Secure`, `SameSite=Strict` (`main.py:270-272`) | **APROVADO** com ressalva P3 |
| Cache de dados privados | SW não guarda `/api`; apenas shell, assets e ícones (`sw.js:2-4,63`) | **APROVADO** |
| Escopo do service worker | Arquivo na raiz, escopo `/`; não intercepta `/api/` | **APROVADO** |
| Execução financeira | Nenhuma rota de ordens, boleta, webhook ou `real-intent`; texto do app reforça “o app não envia ordens” (`StrategyGuide.tsx:85`) | **APROVADO** |
| Nomes de env vars no cliente | `Jarbas.tsx:458` mostra `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `HERMES_BASE_URL` | **REPROVADO** (P23, baixo) |
| Limpeza ampla de caches | `sw.js:31-32` | **REPROVADO** (P14, baixo) |
| Flag de cookie inseguro sem guarda | `main.py:59,271` | **REPROVADO** (P3, médio) |
| Headers/CSP em runtime real | Não verificado em produção | **NÃO EXECUTADO** |
| Isolamento entre usuários em Turso real | Não verificado | **NÃO EXECUTADO** |

**Classificação consolidada de segurança:** **APROVADO** para ausência de segredos e contratos financeiros; **REPROVADO** nos três pontos baixos/médios acima; **NÃO EXECUTADO** para verificação em produção.

---

## 14. Situação do Git

**Baseline inicial (registrado antes da auditoria):**

- Branch: `feature/b3-intelligence-core`.
- `HEAD`: `036a7f9ec32139d925f9675dfe7ab4cd1af14af4`.
- `origin/main`: `036a7f9ec32139d925f9675dfe7ab4cd1af14af4`.
- `HEAD...origin/main`: `0 0` (sem commits à frente ou atrás).
- Modificados (10): `app/lab.py`, `app/main.py`, `app/service.py`, `src/App.tsx`, `src/app.test.tsx`, `src/components/Masthead.tsx`, `src/components/StrategyView.tsx`, `src/services/api.ts`, `src/types.ts`, `tests/test_carteira.py`.
- Não rastreados (6): `app/contracts.py`, `docs/plano-integracao-pwa.md`, `docs/plano-redesign-pwa.md`, `src/components/AppShell.tsx`, `src/envelope.test.tsx`, `src/shell.test.tsx`.
- `git diff --stat`: 10 arquivos, 486 inserções, 169 remoções.
- `git diff --check`: sem erros; apenas avisos de conversão LF→CRLF em `Masthead.tsx`, `StrategyView.tsx` e `test_carteira.py`.

**Operações proibidas — todas NÃO EXECUTADO:** `git reset`, `git clean`, descarte/sobrescrita de alterações, `git commit`, `git push`, deploy.

**Estado final (após a criação deste relatório):**

```text
## feature/b3-intelligence-core...origin/main
 M app/lab.py
 M app/main.py
 M app/service.py
 M src/App.tsx
 M src/app.test.tsx
 M src/components/Masthead.tsx
 M src/components/StrategyView.tsx
 M src/services/api.ts
 M src/types.ts
 M tests/test_carteira.py
?? app/contracts.py
?? docs/plano-integracao-pwa.md
?? docs/plano-redesign-pwa.md
?? docs/relatorio-homologacao-pwa.md
?? src/components/AppShell.tsx
?? src/envelope.test.tsx
?? src/shell.test.tsx
HEAD                 036a7f9ec32139d925f9675dfe7ab4cd1af14af4
origin/main          036a7f9ec32139d925f9675dfe7ab4cd1af14af4
HEAD...origin/main   0  0
git diff --stat      10 arquivos rastreados, 486 inserções, 169 remoções (inalterado)
git diff --check     sem erros; mesmos 3 avisos LF→CRLF do baseline
```

Comparação com o baseline: **mantidos** todos os 10 arquivos modificados e os 6 não rastreados originais; **acrescentado apenas** `docs/relatorio-homologacao-pwa.md`. Nenhum arquivo foi removido ou sobrescrito. Classificação da preservação: **APROVADO**.

---

## 15. Problemas encontrados

| ID | Classificação | Causa | Impacto | Evidência | Solução sugerida |
|---|---|---|---|---|---|
| P1 | **REPROVADO** (médio) | Ordem de prioridade em `label_from_status` | Dado `INDISPONÍVEL` pode virar `SIMULADO`/`OBSERVADO` | `contracts.py:150-159` | Checar indisponibilidade primeiro + teste |
| P2 | **REPROVADO** (baixo) | Campo declarado, nunca calculado | `delay_seconds` sempre `null` | `contracts.py:28`; sem atribuições em `app/` | Calcular ou remover |
| P3 | **REPROVADO** (médio) | Flag de cookie inseguro sem guarda de ambiente | `Secure` pode ser desligado em produção | `main.py:59,271` | Restringir a dev/test |
| P4 | **REPROVADO** (baixo) | Drawer sem focus trap/Escape/retorno de foco | Acessibilidade | `AppShell.tsx:153-165` | Implementar padrão de dialog |
| P5 | **REPROVADO** (baixo) | Jarbas sem foco inicial/Escape | Acessibilidade | `Jarbas.tsx` (sem `Escape`/`focus()`) | Gerenciar foco |
| P6 | **REPROVADO** (baixo) | `aria-label` em `span` | Rótulo pode ser ignorado | `AppShell.tsx:87` | Mover para elemento semântico |
| P7 | **REPROVADO** (baixo) | Bottom nav sem safe-area | Home indicator no iOS | `AppShell.tsx:111-112` | `padding-bottom: env(safe-area-inset-bottom)` |
| P8 | **REPROVADO** (baixo) | Breakpoints CSS ≠ Tailwind | Layout inconsistente | `index.css:263,273` | Unificar tokens de breakpoint |
| P9 | **REPROVADO** (médio) | Erro de status mascarado | Diagnóstico errado | `Jarbas.tsx:458` | Diferenciar erro de configuração |
| P10 | **REPROVADO** (baixo) | Toggle só claro/escuro | Sem volta ao automático | `ThemeToggle.tsx:5-24` | Adicionar terceira opção |
| P11 | **REPROVADO** (médio) | Meta Apple ausente | Standalone no iOS | `index.html:12-14` | Adicionar na Fase 3 |
| P12 | **REPROVADO** (baixo) | Manifest enxuto | Instalação limitada | `manifest.webmanifest:1-16` | Ampliar na Fase 3 |
| P13 | **REPROVADO** (médio) | Chunks fora do pre-cache | Gráfico pode falhar offline | `sw.js:9,17-19` | Incluir chunks na Fase 3 |
| P14 | **REPROVADO** (baixo) | `activate` apaga todos os caches | Colateral na origem | `sw.js:31-32` | Filtrar prefixo `b3-` |
| P15 | **REPROVADO** (médio) | Sem refetch no `online` | Dados desatualizados | `AppStatus.tsx:87-107` | Recarregar resources ao reconectar |
| P16 | **REPROVADO** (baixo) | Docs desatualizadas | Premissa errada (39 rotas) | contagem real = 40 | Atualizar docs |
| P17 | **REPROVADO** (baixo) | Escopo da garantia “GET não grava” ambíguo | Interpretação incorreta | `auth.py:98-111`, `cache.py:139`, `main.py:388` | Explicitar escopo |
| P18 | **REPROVADO** (baixo) | Instalação só após login | Perda de oportunidade | `App.tsx:49,79` | Avaliar fora do Workspace |
| P19 | **REPROVADO** (baixo) | “Ir para o Jarbas” só scroll | Navegação pouco clara | `AppShell.tsx:47-49` | Trocar aba ou dar feedback |
| P20 | **REPROVADO** (baixo) | Dois abridores do drawer | Duplicidade | `Masthead.tsx:16`, `AppShell.tsx:140-141` | Consolidar affordance |
| P21 | **REPROVADO** (baixo) | Contraste possivelmente baixo em `--dp-color-rule` | Legibilidade | `index.css:8` | Medir WCAG e ajustar |
| P22 | **NÃO EXECUTADO** | Safe-zone do maskable não inspecionada | Corte em launcher | ícone existe; imagem não analisada | Validar em Android |
| P23 | **REPROVADO** (baixo) | Nomes de env vars no bundle | Divulgação de configuração, não de valores | `Jarbas.tsx:458` | Mensagem genérica |
| P24 | **NÃO EXECUTADO** | Estado real de produção/Turso/env não verificado | Homologação incompleta | sem acesso | Validar em staging/produção |

Nenhum item foi corrigido automaticamente.

---

## 16. Riscos identificados

1. **Falso senso de homologação:** reexecutar testes verdes não substitui Android/iPhone reais. Classificação: **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL**.
2. **Ruído de configuração em produção:** `B3_INSECURE_COOKIE` e segredos ausentes/presentes podem alterar comportamento de segurança. **NÃO EXECUTADO**.
3. **Interpretação de procedência:** P1 e P2 podem fazer dado indisponível parecer simulado/observado e esconder atraso. **REPROVADO**.
4. **Offline enganoso:** P13 e P15 podem mostrar gráfico antigo ou não atualizado após reconexão. **REPROVADO**.
5. **iOS standalone:** P7 e P11 podem degradar a experiência e gerar reclamos na homologação Apple. **REPROVADO**.
6. **Acessibilidade:** P4/P5/P6/P10/P21 podem impedir uso por teclado/leitor de tela. **REPROVADO**.
7. **Diagnóstico do Jarbas:** P9 pode levar a culpar provedores quando há erro de rede. **REPROVADO**.
8. **Cache colateral:** P14 pode apagar caches de outras apps na mesma origem. **REPROVADO**.
9. **Escopo financeiro:** embora não haja ordens no código, qualquer implementação futura deve passar por autorização explícita. **APROVADO** no estado atual.
10. **Mudanças não commitadas:** 16 arquivos do working tree poderiam ser perdidos se alguém executar operações destrutivas. **APROVADO** na preservação; risco operacional **NÃO EXECUTADO**.

---

## 17. Recomendações

1. **Antes de qualquer dispositivo:** decidir com Jarbas/Joel sobre P1, P3, P9, P11, P13 e P15. Não aplicar correções sem autorização.
2. **Agendar homologação:** executar integralmente os checklists das seções 11 e 12 em Android e iPhone físicos, com registro de versão do SO, navegador e build testado.
3. **Verificar runtime:** confirmar em produção `Secure` do cookie, CSP/headers aplicados, presença de segredos apenas no servidor e conexão Turso ativa.
4. **Documentar:** atualizar `docs/plano-integracao-pwa.md` com o estado real (40 rotas, Fase 1/2 concluídas localmente, problemas acima).
5. **Fase 3:** somente após autorização escrita — manifest ampliado, `apple-mobile-web-app-capable`, página offline, pre-cache de chunks, refetch na reconexão, push/VAPID e revisão de CSP.
6. **Fase 4:** somente após autorização escrita — novas migrations, agentes e cron adicionais. O cron `/api/cron/scan` existente é pré-existente e não foi executado.
7. **Git:** não fazer commit/push/deploy até que a homologação em dispositivo seja aprovada e Joel autorize.
8. **Preservar arquitetura:** continuar com um único gateway, uma única sessão, um único manifest e um único SW `b3-shell-v4`.

---

## 18. Critérios para liberação da Fase 3

| Critério | Evidência necessária | Situação atual |
|---|---|---|
| Fases 1 e 2 revalidadas | `pytest`, lint, Vitest e build verdes nesta auditoria | **APROVADO** |
| Relatório aceito por Joel e Jarbas | Registro de aceite e decisão sobre P1–P24 | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| Nenhuma arquitetura paralela criada | Varredura atual | **APROVADO** |
| Bundle sem segredos/contratos proibidos | Varredura restrita | **APROVADO** com ressalva P23 |
| Problemas P1, P3, P9, P11, P13, P15 triados | Decisão documentada de corrigir/adiar | **NÃO EXECUTADO** |
| Plano de teste em dispositivo agendado | Checklists preenchidos | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| Autorização explícita de Joel para Fase 3 | Registro de autorização | **NÃO EXECUTADO** |

**Conclusão da Fase 3:** **NÃO EXECUTADO / AGUARDANDO AUTORIZAÇÃO.** Nenhuma atividade de Fase 3 foi iniciada nesta rodada.

---

## 19. Critérios para publicação

| Critério | Situação atual | Classificação |
|---|---|---|
| Android checklist integralmente aprovado | Não executado | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| iPhone checklist integralmente aprovado | Não executado | **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL** |
| Smoke em staging/produção (HTML, manifest, SW) | Apenas local | **NÃO EXECUTADO** |
| CSP e headers confirmados em runtime | Apenas configuração estática | **NÃO EXECUTADO** |
| Segredos confirmados apenas no servidor | Estática aprovada; runtime não verificado | **NÃO EXECUTADO** |
| Cookie `Secure` ativo em produção | Código aprovado; flag de risco P3 | **REPROVADO** até verificação |
| Migrations aplicadas por processo autorizado | Nenhuma executada | **NÃO EXECUTADO** |
| Jarbas real respondendo em produção | Não verificado | **NÃO EXECUTADO** |
| Ausência de ordens/boleta/webhook/real-intent | Verificado no código e bundle | **APROVADO** |
| Commit, push e deploy autorizados por Joel | Não autorizados | **NÃO EXECUTADO** |
| Plano de rollback definido | Não fornecido | **NÃO EXECUTADO** |

**Critério final:** a publicação **não está liberada**. O estado correto é **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL**, com itens de runtime classificados como **NÃO EXECUTADO**.

---

**Encerramento:** auditoria executada sem alteração de código, sem commit, push, deploy, migrations, cron, novos agentes, Fase 3, Fase 4 ou operações financeiras. O único arquivo criado nesta rodada é este relatório. Aguardando autorização de Joel Oliveira para as próximas etapas.
