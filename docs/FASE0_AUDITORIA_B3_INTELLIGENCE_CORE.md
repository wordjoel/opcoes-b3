# B3 Opções Pro: Fase 0, auditoria técnica

Data: 02/11/2026. Arquivo guardado fora da pasta do código, que não foi alterada.

## 1. Baseline

| Item | Situação |
|---|---|
| Diretório | `C:\projetos\b3-opcoes\B3-OPCOES-PRO--main (3)\B3-OPCOES-PRO--main` |
| Git local | **Não existe.** A pasta veio de um download em ZIP, sem histórico |
| Remote informado | `yoelzaiyt/B3-OPCOES-PRO-`: **404** sem login, com o Git local e com o `gh` logado como `wordjoel` |
| Repositórios acessíveis | Nenhum com "b3" ou "opco" no nome na conta `wordjoel`; o perfil público de `yoelzaiyt` mostra só `igrejaA` e `athos-track` |
| Branch, HEAD, commits | **BLOQUEADO**: dependem de acesso ao repositório real |
| Testes | **Nenhum** (sem framework e sem arquivos de teste) |
| `tsc --noEmit` | Passa |
| `vite build` | Passa, com bundle de 1.033 kB (aviso de tamanho) |
| `npm audit --omit=dev` | 13 vulnerabilidades: 1 crítica, 8 altas, 2 moderadas, 2 baixas |

Efeitos desta sessão na pasta: `node_modules` criada por `npm ci`, ignorada pelo `.gitignore`. Um `git init` feito antes do Prompt Master foi desfeito (0 objetos, 0 commits). Um `npm audit fix` foi interrompido antes de alterar `package.json` ou `package-lock.json`. Os arquivos do projeto foram comparados com o backup e estão idênticos.

## 2. Arquitetura atual

SPA React 19 + Vite + Tailwind, sem backend. O navegador chama o Gemini direto.

```
main.tsx -> App.tsx (estado e abas)
              |- Sidebar.tsx        menu e "robôs"
              |- Dashboard.tsx      monitor
              |- aba Scanner        dentro do App.tsx
              |- StrategyView.tsx   grade, payoff, boleta
              `- aba Alertas        dentro do App.tsx
constants.ts          ativos e robôs fixos
geminiService.ts      prompt -> JSON da estratégia
firebase-blueprint.json  esquema sem nenhum uso no código
```

## 3. Inventário de funcionalidades

| Funcionalidade | Estado | Evidência |
|---|---|---|
| Navegação e layout responsivo | Pronta (vale preservar) | `App.tsx`, `Sidebar.tsx` |
| Identidade visual | Pronta (vale preservar) | Tailwind, tema escuro |
| Gráfico de preço | Quebrada | Série fixa da PETR4, sem relação com o ativo |
| Sentimento e "IV Terminal" | Quebrada | Textos fixos em `Dashboard.tsx` |
| Scanner | Experimental | Lista 8 ativos fixos e não varre nada |
| Grade de opções | Quebrada | Mesmos valores e códigos BBAS para qualquer ativo |
| Recomendação de estratégia | Quebrada | Números vêm do modelo, sem validação |
| Fallback da IA | Quebrada | Sempre sugere trava de alta, com valores impossíveis em ativos baratos |
| Payoff | Quebrada | 4 pontos fixos, sem cálculo |
| Gregas e custo | Quebrada | Constantes em `StrategyView.tsx` |
| POP | Quebrada | Número devolvido pelo modelo |
| Alertas | Quebrada | Dois textos fixos |
| Robôs | Experimental | Só mudam um texto de status |
| "Enviar Ordem", seletor de layout, abas inferiores | Sem função | Sem handler |
| Persistência e login | Inexistente | Só o blueprint do Firebase |

Erro de domínio no prompt da IA: pede Iron Condor com volatilidade baixa e Straddle com volatilidade alta. Comprar straddle com volatilidade cara e vender condor com ela barata é o inverso do raciocínio usual.

## 4. Mapa de dados e APIs

| Dado | Origem hoje | Real? |
|---|---|---|
| Preço, variação, volume, tendência, volatilidade | `constants.ts` | Não |
| Série intradiária | `Dashboard.tsx` | Não |
| Grade de opções | Valores escritos em `StrategyView.tsx` | Não |
| Estratégia, ganho, perda, POP | Gemini | Não: gerados pelo modelo |
| Notícias, eventos, dividendos, histórico | Não existem | - |

**Nenhuma fonte real de dados de mercado existe no projeto.** A única chamada externa é ao Gemini. Não há rotas de API próprias, banco de dados nem motor quantitativo; `express` e `dotenv` estão instalados sem uso.

Segurança: `vite.config.ts` injeta `GEMINI_API_KEY` no JavaScript enviado ao navegador (confirmado com chave falsa no bundle). `npm run dev` escuta em `0.0.0.0`, expondo o app à rede local.

## 5. Hermes Agent

**Base da análise:** README, AGENTS.md, SECURITY.md, `tools/AGENTS.md`, `cron/AGENTS.md`, `skills/AGENTS.md` e títulos de PRs. **O clone falhou e o site de documentação foi bloqueado, portanto o código-fonte não foi lido.** O projeto usa licença MIT, mas as licenças das dependências não foram verificadas.

| Tema | Hermes (documentado) | B3 hoje | Decisão |
|---|---|---|---|
| Ciclo do agente | Fases em `agent/turn_*.py` | Inexistente | Fazer pipeline tipado, com LLM só no fim |
| Ferramentas | Registro com schema, handler e `check_fn`; toolsets | Inexistente | Adotar o conceito, com allowlist por agente |
| Subagentes | Papéis leaf e orchestrator; profundidade 2; 3 filhos simultâneos | Inexistente | Adotar os limites; os especialistas são módulos, não processos |
| Skills | SKILL.md com versão; sem campo de confiança | Inexistente | Fazer próprio, com testes e aprovação: o Hermes não oferece isso |
| Memória | Memória curada, busca FTS5 em sessões | Inexistente | Adotar FTS5 em SQLite; registrar previsão e resultado separados |
| Agendamento | Execução no máximo uma vez, ledger de horários, catch-up | Inexistente | Adotar as invariantes; é a parte mais reutilizável |
| Provedores | Vários, com seleção explícita e erro sem fallback silencioso | Só Gemini | Adotar interface própria, com fallback visível |
| Segurança | Limite real é o SO; aprovações e guards são heurísticas | Chave exposta | Permissões impostas em código; agentes sem shell |

**Não instalar o Hermes como dependência.** É um agente de uso geral em Python 3.14, com terminal e execução de código, que contradiz a regra de skills sem comandos irrestritos. Adicionaria outro runtime a um projeto TypeScript, e o que serve aqui são poucos conceitos pequenos.

**PRs** (só títulos; nenhum diff ou teste lido; 25 de 157 resultados vistos): #138354, #138697, #140404 e #137680 tratam de skills por projeto e herança, e estavam abertas, logo não são estáveis. #135826 (bloqueio de shell inline em skills da comunidade) estava mergeada e serve só como ideia. Nenhuma é recomendada para reutilização.

## 6. Componentes

- **Reutilizar do B3:** layout, navegação, identidade visual, `utils.ts`, recharts.
- **Substituir:** `geminiService.ts`, valores fixos das telas, painel de robôs, boleta.
- **Desenvolver:** backend, camada de provedores com proveniência, motor quantitativo, contratos dos agentes, supervisor, risco, memória, skills, agendador, auditoria, Intelligence Desk, testes.

## 7. Riscos de integração

| Risco | Impacto | Mitigação |
|---|---|---|
| Repositório real pode diferir do ZIP | Trabalho sobre base errada, histórico incompatível | Obter acesso antes de criar a branch |
| Sem fonte de opções real | Fases 2 a 6 sem dados, só `DADOS INSUFICIENTES` | Definir provedor |
| Licenciamento de dados da B3 | Tempo real exige contrato ou distribuidor | Usar fonte autorizada; aceitar atraso e exibi-lo |
| Dados com atraso | Bid/ask defasados invalidam travas | Marcar idade do dado e bloquear análise quando vencido |
| Histórico de opções | Backtest sem dados perde validade | Mostrar `DADOS INSUFICIENTES` até haver histórico identificado |
| Injeção de prompt por notícias | Conclusão manipulada | Texto externo tratado como dado; agentes de notícia sem ferramentas sensíveis |
| Custo de LLM com 8 agentes | Gasto alto sem ganho | Especialistas determinísticos, LLM só na síntese, com orçamento |
| Monitorar sem tela aberta | Exige máquina sempre ligada | Definir onde roda antes da Fase 4 |
| Escopo muito amplo | Muito código sem validação | Fatias verticais, com status real em cada fase |

## 8. Plano técnico proposto

Princípio central: **os especialistas são módulos TypeScript determinísticos com contratos tipados. O LLM entra só para planejar, explicar e sintetizar.** Assim a regra da "verdade numérica" fica garantida pela estrutura, e o custo fica controlado.

| Fase | Entrega | Condição |
|---|---|---|
| 1 | Docs de arquitetura; contratos (envelope com fonte, horário, premissas, confiança); testes de contrato | Repositório definido |
| 2 | Backend sem chave no navegador; motor quant base; provedores; fluxo Scanner -> Options -> Volatility -> Risk -> Supervisor, com `DADOS INSUFICIENTES` | Provedor para dados reais |
| 3 | Strategy Builder com as 11 estruturas; cenários; backtest | Histórico real |
| 4 | Memória SQLite/FTS5, skills com aprovação, agendador, alertas sem duplicidade | Local de execução |
| 5 | Intelligence Desk | Fases 2 a 4 |
| 6 | Testes de integração, segurança e discordância entre agentes | - |
| 7 | `B3_INTELLIGENCE_CORE_RELATORIO_FINAL.md` | - |

Qualquer push, merge ou deploy continua dependendo de autorização expressa.

## 9. Revisão da proposta em Python (estrutura, contratos, orquestrador)

A proposta chegou cortada na seção 4, no meio de `BlackScholesCalculator.price`. Nada dela foi executado; a revisão é só de leitura. Se aprovada, ela substitui o TypeScript do princípio da seção 8 no backend: a separação entre especialistas determinísticos e LLM continua valendo, e o React permanece na interface.

**Aproveitar:** separação quant/agents/api, FastAPI com Pydantic para contratos, numpy e scipy para cálculo e backtest, e a regra de que risco reprovado derruba a estratégia.

**Corrigir antes de implementar:**

| Ponto | Problema | Correção |
|---|---|---|
| `IntelligenceSupervisor.execute` | `context = await asyncio.gather(...)` troca o contexto por uma lista; a linha seguinte reexecuta os agentes sobre essa lista | Cada agente devolve seu resultado tipado e o supervisor faz o merge |
| `_finalize` | Com `risk` vazio, a estratégia passa sem validação: se o Risk Manager falhar, nada a rejeita | Sem aprovação explícita de risco, não há estratégia apresentável |
| `_finalize` | `.get` falha em `RiskAssessment`, que é modelo Pydantic e não dict | Usar o tipo definido |
| `_finalize` | Divergência entre agentes é só comentário; `confidence_score` nunca é definido | Implementar detecção de divergência e a regra de confiança |
| `BaseAgent.run` | Erro vira texto no contexto e o fluxo segue | Falha explícita, que marca os dados dependentes como insuficientes |
| `MarketSnapshot.source` | O padrão `"REAL"` rotula como real um dado sem origem declarada | Campo obrigatório, com horário de coleta, horário de mercado, atraso e validação |
| `OptionChainLeg` | IV e gregas obrigatórias forçam inventar valor quando não há preço | Campos opcionais, calculados pelo motor |
| `StrategyProposal` | `max_profit` e `max_loss` em `float` não representam ganho ilimitado; `legs` é dict livre | Tipo que aceite ilimitado e modelo próprio para as pernas |
| `BlackScholesCalculator` | Juros padrão de 3% não servem ao Brasil e passariam despercebidos | Taxa obrigatória, com fonte e data |
| `d1_d2` | Com `T <= 0` devolve `(0, 0)`, o que levaria a call a 0,5 x (S - K) em vez do valor intrínseco | Tratar o vencimento antes de calcular d1 e d2 |
| `fallback_mock.py` | Fica entre os provedores de produção, contra a regra de simulados só em testes | Mover para fixtures de teste, sem fallback em produção |
| Estrutura | Faltam provedores de LLM com orçamento, agendador e fila, auditoria e permissões, e a posição do frontend | Acrescentar os módulos e definir o local do React |
