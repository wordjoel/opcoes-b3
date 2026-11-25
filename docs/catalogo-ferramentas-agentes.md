# Catálogo de Ferramentas, Agentes, APIs e Módulos Úteis — B3 Opções Pro

**Data:** 2026-11-24  
**Finalidade:** registro de referência para apoio ao desenvolvimento, auditoria e homologação do PWA.  
**Escopo:** **catálogo estático**. Nenhum item abaixo foi integrado ao runtime da aplicação, ao Jarbas, ao gateway `src/services/api.ts`, ao banco Turso ou ao service worker.

> Os links foram transcritos da lista fornecida. A existência, licença e estado atual de cada repositório **não foram verificados nesta rodada** — classificação global **NÃO VERIFICADO** até confirmação.

## Legenda de classificação

| Classificação | Significado |
|---|---|
| **RECOMENDADO** | Útil como apoio ao desenvolvimento/documentação, sem alterar a arquitetura aprovada. |
| **AVALIAR** | Pode ser útil, mas exige análise de segurança, licença, custo ou escopo antes de qualquer adoção. |
| **FORA DO ESCOPO** | Não se aplica ao domínio atual ou conflita com as restrições do projeto. |
| **NÃO VERIFICADO** | Sem URL informada ou sem confirmação de existência/adequação nesta rodada. |

---

## 1. Agentes de IA & Codificação (itens 1–31)

| # | Recurso | Link | Utilidade no projeto | Classificação |
|---:|---|---|---|---|
| 1 | All-Hands-AI/OpenHands | github.com/All-Hands-AI/OpenHands | Automação de reparo/refatoração em sandbox; apenas em cópia de trabalho | **AVALIAR** |
| 2 | anthropics/claude-code | github.com/anthropics/claude-code | Referência de fluxo de codificação assistida; o ambiente atual já é equivalente | **RECOMENDADO** |
| 3 | anthropics/claude-cookbooks | github.com/anthropics/claude-cookbooks | Padrões de prompt, avaliação e segurança para o Jarbas | **RECOMENDADO** |
| 4 | anthropics/claude-quickstarts | github.com/anthropics/claude-quickstarts | Exemplos de agentes e RAG para estudos | **AVALIAR** |
| 5 | anthropics/claude-desktop-extensions | github.com/anthropics/claude-desktop-extensions | Extensões/MCP para desktop; não alterar o app | **AVALIAR** |
| 6 | hesreallyhim/awesome-claude-code | github.com/hesreallyhim/awesome-claude-code | Catálogo de comandos, skills e boas práticas | **RECOMENDADO** |
| 7 | SuperClaude-Org/SuperClaude_Framework | github.com/SuperClaude-Org/SuperClaude_Framework | Workflows estruturados; avaliar antes de adotar | **AVALIAR** |
| 8 | musistudio/claude-code-router | github.com/musistudio/claude-code-router | Roteamento de modelos; risco de expor configuração se mal usado | **AVALIAR** |
| 9 | eyaltoledano/claude-task-master | github.com/eyaltoledano/claude-task-master | Gestão de tarefas e fases; útil para controlar Fase 3/Fase 4 | **RECOMENDADO** |
| 10 | Doriandarko/claude-engineer | github.com/Doriandarko/claude-engineer | Engenharia de prompts e papéis | **AVALIAR** |
| 11 | parallaxsys/claude-swarm | github.com/parallaxsys/claude-swarm | Múltiplos agentes — conflita com “um único Jarbas” | **FORA DO ESCOPO** |
| 12 | zebbern/claude-dev-tools | github.com/zebbern/claude-dev-tools | Utilitários de desenvolvimento | **AVALIAR** |
| 13 | continuedev/continue | github.com/continuedev/continue | Assistant de IDE para revisão de código | **RECOMENDADO** |
| 14 | cline/cline | github.com/cline/cline | Assistant de IDE com controle de mudanças | **RECOMENDADO** |
| 15 | OpenInterpreter/open-interpreter | github.com/OpenInterpreter/open-interpreter | Execução de código; somente em ambiente isolado | **AVALIAR** |
| 16 | Aider-AI/aider | github.com/Aider-AI/aider | Refatoração com consciência de Git; cuidado para não criar commits automáticos | **RECOMENDADO** |
| 17 | OpenDevin/OpenDevin | github.com/OpenDevin/OpenDevin | Projeto antigo correlato a OpenHands; avaliar equivalência | **AVALIAR** |
| 18 | Tencent/LoopForge | github.com/Tencent/LoopForge | Framework de agentes; não verificado | **NÃO VERIFICADO** |
| 19 | NousResearch/hermes-agent | github.com/NousResearch/hermes-agent | **Não confundir** com o Hermes do Jarbas: aqui é agente autônomo | **FORA DO ESCOPO** |
| 20 | alexspunt/pi-agent-computer-use | github.com/alexspunt/pi-agent-computer-use | Computer use com risco de ações financeiras inadvertidas | **FORA DO ESCOPO** |
| 21 | zju-real/agent-g2 | github.com/zju-real/agent-g2 | Agente geral; não verificado | **NÃO VERIFICADO** |
| 22 | erensrtky/cogit | github.com/erensrtky/cogit | Agente de raciocínio; não verificado | **NÃO VERIFICADO** |
| 23 | NiazMorshed2007/reanimate | github.com/NiazMorshed2007/reanimate | Finalidade não confirmada | **NÃO VERIFICADO** |
| 24 | tradermonty/claude-trading-skills | github.com/tradermonty/claude-trading-skills | Skills de trading — operações financeiras são proibidas | **FORA DO ESCOPO** |
| 25 | 🆕 pingdotgg/t3code | github.com/pingdotgg/t3code | Novo recurso; não verificado | **NÃO VERIFICADO** |
| 26 | 🆕 webbrain-one/webbrain | github.com/webbrain-one/webbrain | Novo recurso; não verificado | **NÃO VERIFICADO** |
| 27 | 🆕 Mercury Agent | sem URL fornecida | Agente com memória local; avaliar apenas como estudo | **NÃO VERIFICADO** |
| 28 | 🆕 Hoblaud | sem URL fornecida | Escritório virtual para agentes; sem utilidade no domínio atual | **FORA DO ESCOPO** |
| 29 | 🆕 LifeOS | sem URL fornecida | Sistema operacional de vida; fora do escopo | **FORA DO ESCOPO** |
| 30 | 🆕 Qwen Audio Agent | sem URL fornecida | Áudio em tempo real — pode inspirar a voz do Jarbas | **AVALIAR** |
| 31 | 🆕 qiaomu-seo | sem URL fornecida | SEO; fora do escopo do produto | **FORA DO ESCOPO** |

---

## 2. Ferramentas, Utilitários & Sistemas (itens 32–50)

| # | Recurso | Link | Utilidade no projeto | Classificação |
|---:|---|---|---|---|
| 32 | sindresorhus/awesome | github.com/sindresorhus/awesome | Curadoria geral de ferramentas | **RECOMENDADO** |
| 33 | public-apis/public-apis | github.com/public-apis/public-apis | Fontes públicas para estudo de integrações — **somente leitura** | **RECOMENDADO** |
| 34 | ripienaar/free-for-dev | github.com/ripienaar/free-for-dev | Serviços gratuitos para desenvolvimento/CI | **RECOMENDADO** |
| 35 | D4Vinci/Scrapling | github.com/D4Vinci/Scrapling | Coleta de dados; respeitar ToS e regras da B3 | **AVALIAR** |
| 36 | ollama/ollama | github.com/ollama/ollama | Modelos locais para testes offline de prompt | **AVALIAR** |
| 37 | schollz/croc | github.com/schollz/croc | Transferência simples de artefatos entre máquinas | **AVALIAR** |
| 38 | hyprwm/Hyprland | github.com/hyprwm/Hyprland | Gerenciador de janelas Linux; fora do escopo | **FORA DO ESCOPO** |
| 39 | openobserve/openobserve | github.com/openobserve/openobserve | Observabilidade; não enviar dados privados de usuário | **AVALIAR** |
| 40 | goauthentik/authentik | github.com/goauthentik/authentik | IAM; hoje existe uma única sessão `b3_session` — não duplicar | **AVALIAR** |
| 41 | hieunc229/mailflare | github.com/hieunc229/mailflare | E-mail descartável; fora do escopo | **FORA DO ESCOPO** |
| 42 | aws/aws-emulator | github.com/aws/aws-emulator | Projeto usa Vercel/Turso; emulador AWS não se aplica | **FORA DO ESCOPO** |
| 43 | jendrikseipp/vulture | github.com/jendrikseipp/vulture | Detecção de código morto no frontend/backend | **RECOMENDADO** |
| 44 | erKamyaman/rust-anything | github.com/erkamyaman/rust-anything | Não verificado | **NÃO VERIFICADO** |
| 45 | RoutineMiku/apks (ApkStart) | github.com/RoutineMiku/apks | Apoio à homologação Android; avaliar origem dos APKs | **AVALIAR** |
| 46 | gxurav1710/YouPI-PG | github.com/gxurav1710/YouPI-PG | Não verificado | **NÃO VERIFICADO** |
| 47 | GoogleChrome/modern-web-guidance | github.com/GoogleChrome/modern-web-guidance | Guia moderno de Web/PWA — alinhado ao Fase 3 | **RECOMENDADO** |
| 48 | SlimToolkit (DockerSlim) | github.com/slimtoolkit/slim | Redução de imagens, se houver containerização futura | **AVALIAR** |
| 49 | simpsoka/zigzag | github.com/simpsoka/zigzag | Não verificado | **NÃO VERIFICADO** |
| 50 | 🆕 localThings | sem URL fornecida | Integração com eletrodomésticos; fora do escopo | **FORA DO ESCOPO** |

---

## 3. Modelos, RAG, Dados & Pesquisa (itens 51–64)

| # | Recurso | Link | Utilidade no projeto | Classificação |
|---:|---|---|---|---|
| 51 | Shubhamsaboo/awesome-llm-apps | github.com/Shubhamsaboo/awesome-llm-apps | Padrões de aplicações LLM para estudo do Jarbas | **RECOMENDADO** |
| 52 | punkpeye/awesome-mcp-servers | github.com/punkpeye/awesome-mcp-servers | Servidores MCP como referência, sem duplicar o gateway | **RECOMENDADO** |
| 53 | liuyoshio/mcp-compass | github.com/liuyoshio/mcp-compass | Descoberta/avaliação de MCP | **AVALIAR** |
| 54 | anaisbetts/mcp-installer | github.com/anaisbetts/mcp-installer | Instalação de MCP; não usar em produção sem auditoria | **AVALIAR** |
| 55 | idosal/mcphub | github.com/idosal/mcphub | Hub de MCP; centralizar configuração sem expor segredos | **AVALIAR** |
| 56 | NVIDIA/SkillEvaluator | github.com/NVIDIA/SkillEvaluator | Avaliação de habilidades/respostas do Jarbas | **RECOMENDADO** |
| 57 | edge0-ai/edge0 | github.com/edge0-ai/edge0 | Não verificado | **NÃO VERIFICADO** |
| 58 | openbitsys/bitdecoding-fp4 | github.com/openbitsys/bitdecoding-fp4 | Decodificação FP4; fora do escopo | **FORA DO ESCOPO** |
| 59 | Zyphra/ZONOS3-Mini | github.com/Zyphra/ZONOS3-Mini | Modelo de voz; pode inspirar síntese do Jarbas | **AVALIAR** |
| 60 | ZhikaiXu24/DAS | github.com/zhikaixu24/das | Não verificado | **NÃO VERIFICADO** |
| 61 | 🆕 opendatalab/MinerU | github.com/opendatalab/MinerU | OCR/extração de documentos; útil para relatórios e PDFs | **RECOMENDADO** |
| 62 | 🆕 InferSSD | sem URL fornecida | Inferência direta do SSD; avaliar custo/latência | **AVALIAR** |
| 63 | 🆕 RAG-Anything | sem URL fornecida | RAG “tudo em um”; **não** criar banco paralelo ao Turso | **AVALIAR** |
| 64 | 🆕 RapidOCR | sem URL fornecida | OCR leve — bom candidato para Scanner | **RECOMENDADO** |

---

## 4. Design, Web, Multimídia & Outros (itens 65–82)

| # | Recurso | Link | Utilidade no projeto | Classificação |
|---:|---|---|---|---|
| 65 | nexu-io/open-design | github.com/nexu-io/open-design | Design system; avaliar compatibilidade com tokens `--dp-*` | **AVALIAR** |
| 66 | meta/astryx | github.com/meta/astryx | Não verificado | **NÃO VERIFICADO** |
| 67 | anthropics/knowledge-work-plugins | github.com/anthropics/knowledge-work-plugins | Plugins para Documentação/conhecimento do time | **RECOMENDADO** |
| 68 | anthropics/financial-services | github.com/anthropics/financial-services | Referência financeira **somente educacional**; risco de operações reais | **AVALIAR** |
| 69 | coreyhaines31/marketingskills | github.com/coreyhaines31/marketingskills | Marketing; fora do escopo | **FORA DO ESCOPO** |
| 70 | yakhyo/uniface | github.com/yakhyo/uniface | Reconhecimento facial; privacidade e fora do escopo | **FORA DO ESCOPO** |
| 71 | hacksider/Deep-Live-Cam | github.com/hacksider/Deep-Live-Cam | Deepfake — risco reputacional e de privacidade | **FORA DO ESCOPO** |
| 72 | nota-daw/nota | github.com/nota-daw/nota | DAW; fora do escopo | **FORA DO ESCOPO** |
| 73 | xiao-ye-codes/code-animation-prompts | github.com/xiao-ye-codes/code-animation-prompts | Animação de código para documentação visual | **AVALIAR** |
| 74 | bradautomates/head-of-content | github.com/bradautomates/head-of-content | Conteúdo/marketing; fora do escopo | **FORA DO ESCOPO** |
| 75 | xToshiro/MediaFinder | github.com/xToshiro/MediaFinder | Busca de mídia; fora do escopo | **FORA DO ESCOPO** |
| 76 | qybaibai/bla | github.com/qybaibai/bla | Não verificado | **NÃO VERIFICADO** |
| 77 | agentes-chat/agentes-chat | github.com/agentes-chat/agentes-chat | Agentes de chat; avaliar sem substituir o Jarbas | **AVALIAR** |
| 78 | zeenie-ai/opencompany | github.com/zeenie-ai/opencompany | Empresa simulada de agentes; fora do escopo | **FORA DO ESCOPO** |
| 79 | FERAL-AI/feral-ai | github.com/feral-ai/feral-ai | Não verificado | **NÃO VERIFICADO** |
| 80 | waldboulanouar/agent-aware | github.com/waldboulanouar/agent-aware | Consciência de agentes; avaliar apenas como estudo | **AVALIAR** |
| 81 | wangzan101/mika | github.com/wangzan101/mika | Não verificado | **NÃO VERIFICADO** |
| 82 | storytold/craft-anything | github.com/storytold/craft-anything | Criação assistida; avaliar uso em documentação | **AVALIAR** |

---

## 5. Módulos e funções úteis sugeridas

O módulo `src/lib/toolsCatalog.ts` foi acrescentado nesta rodada como **catálogo estático tipado**. Ele não executa agentes, não faz chamadas de rede e não é importado por nenhum componente do app.

| Módulo/função | Estado | Finalidade |
|---|---|---|
| `TOOLS`, `byCategory`, `recommended`, `findTool`, `searchTools`, `countByCategory` | **IMPLEMENTADO** (`src/lib/toolsCatalog.ts`) | Consulta local do catálogo para futura tela/documentação |
| `labelPolicy` — priorizar `INDISPONÍVEL` sobre `SIMULADO`/`OBSERVADO` | **NÃO IMPLEMENTADO** | Resolve P1 |
| `priceFreshness` — calcular `delay_seconds` | **NÃO IMPLEMENTADO** | Resolve P2 |
| `secureCookieGuard` — impedir `B3_INSECURE_COOKIE` em produção | **NÃO IMPLEMENTADO** | Resolve P3 |
| `a11yDialog` — focus trap/Escape/retorno de foco | **NÃO IMPLEMENTADO** | Resolve P4/P5 |
| `safeAreaBottom` — `env(safe-area-inset-bottom)` na nav inferior | **NÃO IMPLEMENTADO** | Resolve P7 |
| `offlineChunkWarmer` — incluir chunks dinâmicos no pre-cache | **NÃO IMPLEMENTADO** | Resolve P13 (Fase 3) |
| `reconnectRefetch` — recarregar recursos ao voltar online | **NÃO IMPLEMENTADO** | Resolve P15 (Fase 3) |
| `evidenceExport` — exportar bundle de evidências da auditoria | **NÃO IMPLEMENTADO** | Apoio à homologação |
| `catalogMCP` — registrar servidores MCP permitidos | **NÃO IMPLEMENTADO** | Exige autorização e auditoria de segredos |

**Nenhuma** dessas funções foi ligada ao runtime sem autorização específica.

---

## 6. Prioridade sugerida de avaliação

1. `anthropics/claude-code`, `hesreallyhim/awesome-claude-code`, `eyaltoledano/claude-task-master` — fluxo de trabalho e governança de fases.
2. `continuedev/continue`, `cline/cline`, `Aider-AI/aider` — revisão e refatoração assistida com Git.
3. `public-apis/public-apis`, `ripienaar/free-for-dev` — fontes e serviços gratuitos, sempre somente leitura.
4. `GoogleChrome/modern-web-guidance` — alinhamento com PWA/Fase 3.
5. `punkpeye/awesome-mcp-servers`, `idosal/mcphub` — MCP sem duplicar gateway.
6. `NVIDIA/SkillEvaluator` — avaliação objetiva das respostas do Jarbas.
7. `opendatalab/MinerU`, `RapidOCR` — OCR para documentos e Scanner.
8. `jendrikseipp/vulture`, `SlimToolkit` — qualidade e enxugamento de código/imagens.
9. `anthropics/knowledge-work-plugins` — documentação do time.
10. `anthropics/financial-services` — **apenas** como referência educacional, nunca para execução financeira.

---

## 7. Regras de segurança e arquitetura

- Nenhum item deste catálogo é dependência de produção do PWA.
- Não criar segundo agente, segundo gateway, segundo banco, segunda sessão, segundo manifest ou segundo service worker.
- Não mover chaves de IA para variáveis `VITE_*`; segredos permanecem apenas no backend.
- Não implementar ordens, boleta, webhook, `real-intent` ou qualquer execução financeira.
- Não executar Fase 3, Fase 4, migrations, cron adicional ou deploy sem autorização explícita.
- Verificar licença, URL e manutenção de cada repositório antes de qualquer adoção.
- A homologação em Android/iPhone continua **AGUARDANDO VALIDAÇÃO PRÁTICA EM AMBIENTE REAL**.

---

**Resultado desta rodada:** documentação criada e módulo estático implementado. Nenhuma integração em runtime, nenhuma mudança de segurança e nenhuma operação financeira.
