/**
 * Catálogo estático de ferramentas, agentes, APIs e módulos úteis.
 *
 * Este arquivo NÃO executa agentes, NÃO faz chamadas de rede e NÃO é importado
 * por nenhum componente do app. Ele apenas tipa a lista de referência descrita
 * em docs/catalogo-ferramentas-agentes.md para consultas locais futuras.
 */

export type ToolCategory = 'agentes' | 'utilitarios' | 'modelos' | 'design';

export type ToolStatus = 'RECOMENDADO' | 'AVALIAR' | 'FORA_DO_ESCOPO' | 'NAO_VERIFICADO';

export interface ToolEntry {
  id: number;
  name: string;
  url: string | null;
  category: ToolCategory;
  status: ToolStatus;
  note: string;
}

export const CATEGORY_LABELS: Record<ToolCategory, string> = {
  agentes: 'Agentes de IA & Codificação',
  utilitarios: 'Ferramentas, Utilitários & Sistemas',
  modelos: 'Modelos, RAG, Dados & Pesquisa',
  design: 'Design, Web, Multimídia & Outros',
};

export const TOOLS: readonly ToolEntry[] = [
  { id: 1, name: 'All-Hands-AI/OpenHands', url: 'https://github.com/All-Hands-AI/OpenHands', category: 'agentes', status: 'AVALIAR', note: 'Automação de engenharia em sandbox; usar só em cópia de trabalho.' },
  { id: 2, name: 'anthropics/claude-code', url: 'https://github.com/anthropics/claude-code', category: 'agentes', status: 'RECOMENDADO', note: 'Referência de fluxo de codificação assistida.' },
  { id: 3, name: 'anthropics/claude-cookbooks', url: 'https://github.com/anthropics/claude-cookbooks', category: 'agentes', status: 'RECOMENDADO', note: 'Padrões de prompt e avaliação para o Jarbas.' },
  { id: 4, name: 'anthropics/claude-quickstarts', url: 'https://github.com/anthropics/claude-quickstarts', category: 'agentes', status: 'AVALIAR', note: 'Exemplos de agentes e RAG.' },
  { id: 5, name: 'anthropics/claude-desktop-extensions', url: 'https://github.com/anthropics/claude-desktop-extensions', category: 'agentes', status: 'AVALIAR', note: 'Extensões/MCP para desktop; não alterar o app.' },
  { id: 6, name: 'hesreallyhim/awesome-claude-code', url: 'https://github.com/hesreallyhim/awesome-claude-code', category: 'agentes', status: 'RECOMENDADO', note: 'Catálogo de comandos, skills e boas práticas.' },
  { id: 7, name: 'SuperClaude-Org/SuperClaude_Framework', url: 'https://github.com/SuperClaude-Org/SuperClaude_Framework', category: 'agentes', status: 'AVALIAR', note: 'Workflows estruturados; avaliar antes de adotar.' },
  { id: 8, name: 'musistudio/claude-code-router', url: 'https://github.com/musistudio/claude-code-router', category: 'agentes', status: 'AVALIAR', note: 'Roteamento de modelos; risco se mal configurado.' },
  { id: 9, name: 'eyaltoledano/claude-task-master', url: 'https://github.com/eyaltoledano/claude-task-master', category: 'agentes', status: 'RECOMENDADO', note: 'Gestão de tarefas e fases.' },
  { id: 10, name: 'Doriandarko/claude-engineer', url: 'https://github.com/Doriandarko/claude-engineer', category: 'agentes', status: 'AVALIAR', note: 'Engenharia de prompts e papéis.' },
  { id: 11, name: 'parallaxsys/claude-swarm', url: 'https://github.com/parallaxsys/claude-swarm', category: 'agentes', status: 'FORA_DO_ESCOPO', note: 'Múltiplos agentes conflitam com um único Jarbas.' },
  { id: 12, name: 'zebbern/claude-dev-tools', url: 'https://github.com/zebbern/claude-dev-tools', category: 'agentes', status: 'AVALIAR', note: 'Utilitários de desenvolvimento.' },
  { id: 13, name: 'continuedev/continue', url: 'https://github.com/continuedev/continue', category: 'agentes', status: 'RECOMENDADO', note: 'Assistente de IDE para revisão de código.' },
  { id: 14, name: 'cline/cline', url: 'https://github.com/cline/cline', category: 'agentes', status: 'RECOMENDADO', note: 'Assistente de IDE com controle de mudanças.' },
  { id: 15, name: 'OpenInterpreter/open-interpreter', url: 'https://github.com/OpenInterpreter/open-interpreter', category: 'agentes', status: 'AVALIAR', note: 'Execução de código; somente em ambiente isolado.' },
  { id: 16, name: 'Aider-AI/aider', url: 'https://github.com/Aider-AI/aider', category: 'agentes', status: 'RECOMENDADO', note: 'Refatoração com consciência de Git.' },
  { id: 17, name: 'OpenDevin/OpenDevin', url: 'https://github.com/OpenDevin/OpenDevin', category: 'agentes', status: 'AVALIAR', note: 'Projeto antigo correlato a OpenHands.' },
  { id: 18, name: 'Tencent/LoopForge', url: 'https://github.com/Tencent/LoopForge', category: 'agentes', status: 'NAO_VERIFICADO', note: 'Framework de agentes não verificado.' },
  { id: 19, name: 'NousResearch/hermes-agent', url: 'https://github.com/NousResearch/hermes-agent', category: 'agentes', status: 'FORA_DO_ESCOPO', note: 'Agente autônomo; não é o provedor Hermes do Jarbas.' },
  { id: 20, name: 'alexspunt/pi-agent-computer-use', url: 'https://github.com/alexspunt/pi-agent-computer-use', category: 'agentes', status: 'FORA_DO_ESCOPO', note: 'Computer use com risco de ações financeiras.' },
  { id: 21, name: 'zju-real/agent-g2', url: 'https://github.com/zju-real/agent-g2', category: 'agentes', status: 'NAO_VERIFICADO', note: 'Agente geral não verificado.' },
  { id: 22, name: 'erensrtky/cogit', url: 'https://github.com/erensrtky/cogit', category: 'agentes', status: 'NAO_VERIFICADO', note: 'Agente de raciocínio não verificado.' },
  { id: 23, name: 'NiazMorshed2007/reanimate', url: 'https://github.com/NiazMorshed2007/reanimate', category: 'agentes', status: 'NAO_VERIFICADO', note: 'Finalidade não confirmada.' },
  { id: 24, name: 'tradermonty/claude-trading-skills', url: 'https://github.com/tradermonty/claude-trading-skills', category: 'agentes', status: 'FORA_DO_ESCOPO', note: 'Skills de trading: operações financeiras proibidas.' },
  { id: 25, name: 'pingdotgg/t3code', url: 'https://github.com/pingdotgg/t3code', category: 'agentes', status: 'NAO_VERIFICADO', note: 'Recurso novo não verificado.' },
  { id: 26, name: 'webbrain-one/webbrain', url: 'https://github.com/webbrain-one/webbrain', category: 'agentes', status: 'NAO_VERIFICADO', note: 'Recurso novo não verificado.' },
  { id: 27, name: 'Mercury Agent', url: null, category: 'agentes', status: 'NAO_VERIFICADO', note: 'Agente com memória local; sem URL fornecida.' },
  { id: 28, name: 'Hoblaud', url: null, category: 'agentes', status: 'FORA_DO_ESCOPO', note: 'Escritório virtual para agentes; sem utilidade no domínio.' },
  { id: 29, name: 'LifeOS', url: null, category: 'agentes', status: 'FORA_DO_ESCOPO', note: 'Sistema operacional de vida; fora do escopo.' },
  { id: 30, name: 'Qwen Audio Agent', url: null, category: 'agentes', status: 'AVALIAR', note: 'Áudio em tempo real; pode inspirar a voz do Jarbas.' },
  { id: 31, name: 'qiaomu-seo', url: null, category: 'agentes', status: 'FORA_DO_ESCOPO', note: 'Agente de SEO; fora do escopo.' },

  { id: 32, name: 'sindresorhus/awesome', url: 'https://github.com/sindresorhus/awesome', category: 'utilitarios', status: 'RECOMENDADO', note: 'Curadoria geral de ferramentas.' },
  { id: 33, name: 'public-apis/public-apis', url: 'https://github.com/public-apis/public-apis', category: 'utilitarios', status: 'RECOMENDADO', note: 'APIs públicas para estudo; somente leitura.' },
  { id: 34, name: 'ripienaar/free-for-dev', url: 'https://github.com/ripienaar/free-for-dev', category: 'utilitarios', status: 'RECOMENDADO', note: 'Serviços gratuitos para desenvolvimento e CI.' },
  { id: 35, name: 'D4Vinci/Scrapling', url: 'https://github.com/D4Vinci/Scrapling', category: 'utilitarios', status: 'AVALIAR', note: 'Coleta de dados; respeitar ToS e regras da B3.' },
  { id: 36, name: 'ollama/ollama', url: 'https://github.com/ollama/ollama', category: 'utilitarios', status: 'AVALIAR', note: 'Modelos locais para testes de prompt.' },
  { id: 37, name: 'schollz/croc', url: 'https://github.com/schollz/croc', category: 'utilitarios', status: 'AVALIAR', note: 'Transferência de artefatos entre máquinas.' },
  { id: 38, name: 'hyprwm/Hyprland', url: 'https://github.com/hyprwm/Hyprland', category: 'utilitarios', status: 'FORA_DO_ESCOPO', note: 'Gerenciador de janelas Linux; fora do escopo.' },
  { id: 39, name: 'openobserve/openobserve', url: 'https://github.com/openobserve/openobserve', category: 'utilitarios', status: 'AVALIAR', note: 'Observabilidade; não enviar dados privados.' },
  { id: 40, name: 'goauthentik/authentik', url: 'https://github.com/goauthentik/authentik', category: 'utilitarios', status: 'AVALIAR', note: 'IAM; não duplicar a sessão b3_session.' },
  { id: 41, name: 'hieunc229/mailflare', url: 'https://github.com/hieunc229/mailflare', category: 'utilitarios', status: 'FORA_DO_ESCOPO', note: 'E-mail descartável; fora do escopo.' },
  { id: 42, name: 'aws/aws-emulator', url: 'https://github.com/aws/aws-emulator', category: 'utilitarios', status: 'FORA_DO_ESCOPO', note: 'Emulador AWS; o projeto usa Vercel/Turso.' },
  { id: 43, name: 'jendrikseipp/vulture', url: 'https://github.com/jendrikseipp/vulture', category: 'utilitarios', status: 'RECOMENDADO', note: 'Detecção de código morto.' },
  { id: 44, name: 'erKamyaman/rust-anything', url: 'https://github.com/erkamyaman/rust-anything', category: 'utilitarios', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 45, name: 'RoutineMiku/apks (ApkStart)', url: 'https://github.com/RoutineMiku/apks', category: 'utilitarios', status: 'AVALIAR', note: 'Apoio à homologação Android; avaliar origem dos APKs.' },
  { id: 46, name: 'gxurav1710/YouPI-PG', url: 'https://github.com/gxurav1710/YouPI-PG', category: 'utilitarios', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 47, name: 'GoogleChrome/modern-web-guidance', url: 'https://github.com/GoogleChrome/modern-web-guidance', category: 'utilitarios', status: 'RECOMENDADO', note: 'Guia moderno de Web/PWA.' },
  { id: 48, name: 'SlimToolkit (DockerSlim)', url: 'https://github.com/slimtoolkit/slim', category: 'utilitarios', status: 'AVALIAR', note: 'Redução de imagens, se houver containerização.' },
  { id: 49, name: 'simpsoka/zigzag', url: 'https://github.com/simpsoka/zigzag', category: 'utilitarios', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 50, name: 'localThings', url: null, category: 'utilitarios', status: 'FORA_DO_ESCOPO', note: 'Eletrodomésticos Samsung; fora do escopo.' },

  { id: 51, name: 'Shubhamsaboo/awesome-llm-apps', url: 'https://github.com/Shubhamsaboo/awesome-llm-apps', category: 'modelos', status: 'RECOMENDADO', note: 'Padrões de aplicações LLM.' },
  { id: 52, name: 'punkpeye/awesome-mcp-servers', url: 'https://github.com/punkpeye/awesome-mcp-servers', category: 'modelos', status: 'RECOMENDADO', note: 'Servidores MCP como referência; não duplicar gateway.' },
  { id: 53, name: 'liuyoshio/mcp-compass', url: 'https://github.com/liuyoshio/mcp-compass', category: 'modelos', status: 'AVALIAR', note: 'Descoberta e avaliação de MCP.' },
  { id: 54, name: 'anaisbetts/mcp-installer', url: 'https://github.com/anaisbetts/mcp-installer', category: 'modelos', status: 'AVALIAR', note: 'Instalação de MCP; não usar em produção sem auditoria.' },
  { id: 55, name: 'idosal/mcphub', url: 'https://github.com/idosal/mcphub', category: 'modelos', status: 'AVALIAR', note: 'Hub de MCP; sem expor segredos.' },
  { id: 56, name: 'NVIDIA/SkillEvaluator', url: 'https://github.com/NVIDIA/SkillEvaluator', category: 'modelos', status: 'RECOMENDADO', note: 'Avaliação de respostas do Jarbas.' },
  { id: 57, name: 'edge0-ai/edge0', url: 'https://github.com/edge0-ai/edge0', category: 'modelos', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 58, name: 'openbitsys/bitdecoding-fp4', url: 'https://github.com/openbitsys/bitdecoding-fp4', category: 'modelos', status: 'FORA_DO_ESCOPO', note: 'Decodificação FP4; fora do escopo.' },
  { id: 59, name: 'Zyphra/ZONOS3-Mini', url: 'https://github.com/Zyphra/ZONOS3-Mini', category: 'modelos', status: 'AVALIAR', note: 'Modelo de voz para a síntese do Jarbas.' },
  { id: 60, name: 'ZhikaiXu24/DAS', url: 'https://github.com/zhikaixu24/das', category: 'modelos', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 61, name: 'opendatalab/MinerU', url: 'https://github.com/opendatalab/MinerU', category: 'modelos', status: 'RECOMENDADO', note: 'OCR e extração de documentos.' },
  { id: 62, name: 'InferSSD', url: null, category: 'modelos', status: 'AVALIAR', note: 'Inferência direta do SSD; avaliar custo e latência.' },
  { id: 63, name: 'RAG-Anything', url: null, category: 'modelos', status: 'AVALIAR', note: 'RAG tudo-em-um; não criar banco paralelo ao Turso.' },
  { id: 64, name: 'RapidOCR', url: null, category: 'modelos', status: 'RECOMENDADO', note: 'OCR leve; bom candidato para o Scanner.' },

  { id: 65, name: 'nexu-io/open-design', url: 'https://github.com/nexu-io/open-design', category: 'design', status: 'AVALIAR', note: 'Design system; avaliar tokens --dp-*.' },
  { id: 66, name: 'meta/astryx', url: 'https://github.com/meta/astryx', category: 'design', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 67, name: 'anthropics/knowledge-work-plugins', url: 'https://github.com/anthropics/knowledge-work-plugins', category: 'design', status: 'RECOMENDADO', note: 'Plugins para documentação do time.' },
  { id: 68, name: 'anthropics/financial-services', url: 'https://github.com/anthropics/financial-services', category: 'design', status: 'AVALIAR', note: 'Referência apenas educacional; risco financeiro.' },
  { id: 69, name: 'coreyhaines31/marketingskills', url: 'https://github.com/coreyhaines31/marketingskills', category: 'design', status: 'FORA_DO_ESCOPO', note: 'Marketing; fora do escopo.' },
  { id: 70, name: 'yakhyo/uniface', url: 'https://github.com/yakhyo/uniface', category: 'design', status: 'FORA_DO_ESCOPO', note: 'Reconhecimento facial; privacidade e fora do escopo.' },
  { id: 71, name: 'hacksider/Deep-Live-Cam', url: 'https://github.com/hacksider/Deep-Live-Cam', category: 'design', status: 'FORA_DO_ESCOPO', note: 'Deepfake; risco reputacional e de privacidade.' },
  { id: 72, name: 'nota-daw/nota', url: 'https://github.com/nota-daw/nota', category: 'design', status: 'FORA_DO_ESCOPO', note: 'DAW; fora do escopo.' },
  { id: 73, name: 'xiao-ye-codes/code-animation-prompts', url: 'https://github.com/xiao-ye-codes/code-animation-prompts', category: 'design', status: 'AVALIAR', note: 'Animação de código para documentação visual.' },
  { id: 74, name: 'bradautomates/head-of-content', url: 'https://github.com/bradautomates/head-of-content', category: 'design', status: 'FORA_DO_ESCOPO', note: 'Conteúdo e marketing; fora do escopo.' },
  { id: 75, name: 'xToshiro/MediaFinder', url: 'https://github.com/xToshiro/MediaFinder', category: 'design', status: 'FORA_DO_ESCOPO', note: 'Busca de mídia; fora do escopo.' },
  { id: 76, name: 'qybaibai/bla', url: 'https://github.com/qybaibai/bla', category: 'design', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 77, name: 'agentes-chat/agentes-chat', url: 'https://github.com/agentes-chat/agentes-chat', category: 'design', status: 'AVALIAR', note: 'Agentes de chat; não substituir o Jarbas.' },
  { id: 78, name: 'zeenie-ai/opencompany', url: 'https://github.com/zeenie-ai/opencompany', category: 'design', status: 'FORA_DO_ESCOPO', note: 'Empresa simulada de agentes; fora do escopo.' },
  { id: 79, name: 'FERAL-AI/feral-ai', url: 'https://github.com/feral-ai/feral-ai', category: 'design', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 80, name: 'waldboulanouar/agent-aware', url: 'https://github.com/waldboulanouar/agent-aware', category: 'design', status: 'AVALIAR', note: 'Consciência de agentes; apenas estudo.' },
  { id: 81, name: 'wangzan101/mika', url: 'https://github.com/wangzan101/mika', category: 'design', status: 'NAO_VERIFICADO', note: 'Recurso não verificado.' },
  { id: 82, name: 'storytold/craft-anything', url: 'https://github.com/storytold/craft-anything', category: 'design', status: 'AVALIAR', note: 'Criação assistida para documentação.' },
];

/** Filtra o catálogo por categoria. */
export function byCategory(category: ToolCategory): ToolEntry[] {
  return TOOLS.filter((tool) => tool.category === category);
}

/** Retorna apenas os recursos classificados como RECOMENDADO. */
export function recommended(): ToolEntry[] {
  return TOOLS.filter((tool) => tool.status === 'RECOMENDADO');
}

/** Busca um recurso pelo número da lista original. */
export function findTool(id: number): ToolEntry | undefined {
  return TOOLS.find((tool) => tool.id === id);
}

/** Busca por nome ou nota, sem diferenciar maiúsculas de minúsculas. */
export function searchTools(term: string): ToolEntry[] {
  const needle = term.trim().toLocaleLowerCase('pt-BR');
  if (!needle) return [];
  return TOOLS.filter((tool) =>
    `${tool.name} ${tool.note}`.toLocaleLowerCase('pt-BR').includes(needle),
  );
}

/** Contagem de recursos por categoria. */
export function countByCategory(): Record<ToolCategory, number> {
  return {
    agentes: byCategory('agentes').length,
    utilitarios: byCategory('utilitarios').length,
    modelos: byCategory('modelos').length,
    design: byCategory('design').length,
  };
}
