# B3 Opções Pro

Análise de opções da B3 para uso pessoal. Só análise: não existe envio de ordens.

- `src/`: PWA em React
- `api/index.py` e `app/`: API em FastAPI, com login
- `core/`, `data/`, `quant/`: contratos, fonte de dados e motor quantitativo
- `db/`: cliente Turso/SQLite e migrations

Convenções e limitações: `docs/quant-convencoes.md`.

Carteira, gestor de risco, supervisor e registro de decisões: `docs/agentes-estado.md`.

Status visual do projeto (abra no navegador): [docs/status-visual.html](docs/status-visual.html). Versão publicada: https://claude.ai/artifact/AGs4pRu86gzBAscRmCojnv

## Rodar localmente

Na primeira vez, gere a senha e copie as duas linhas para `.env.turso` (modelo em `.env.example`), junto com `B3_INSECURE_COOKIE=1`:

```
.venv/Scripts/python -m scripts.hash_password
.venv/Scripts/python -m db.migrate
```

Em dois terminais:

```
.venv/Scripts/python -m uvicorn app.main:app --port 8000
npm run dev
```

Abra http://127.0.0.1:3000. Sem `BRAPI_API_KEY`, só a PETR4 tem grade de opções.

## Testes

```
.venv/Scripts/python -m pytest
npm run lint
npm test
npm run build
```

## Integração contínua

`.github/workflows/ci.yml` roda pytest com cobertura, checagem de tipos, Vitest e o build da PWA em todo push para `main` e em pull requests.

## Jarbas IA

O Jarbas responde se houver pelo menos um provedor configurado **no servidor**: OpenRouter, Gemini, Groq, Hermes ou qualquer endpoint compatível com `/chat/completions` da OpenAI (`JARBAS_CUSTOM_*`). O Hermes precisa de `HERMES_BASE_URL` e `HERMES_MODEL`; a chave é opcional se o serviço não exigir autenticação. Nenhum segredo entra no navegador.

Se o painel mostrar "Nenhum provedor de IA configurado no servidor", cadastre as variáveis em `.env.turso` (modelo em `.env.example`) e rode:

```
.venv/Scripts/python -m scripts.configurar_vercel --producao
```

O script cadastra também as chaves de IA e as variáveis do Hermes. **Sem `--producao` ele atualiza apenas Preview** — foi essa a causa do Jarbas funcionar em preview e falhar no site publicado. Depois, publique de novo (`npx vercel deploy --prod`) e confirme que `GET /api/jarbas/status` devolve `"available": true`.

Para diagnosticar sem gastar chamada de modelo, abra **Configurações do Jarbas → Testar conexão** (ou `GET /api/jarbas/diagnose`, protegido por login). A sonda consulta cada provedor com timeout de 5 s e devolve apenas `ok`, `reachable`, status HTTP, latência e um motivo genérico — nunca URL, chave ou cabeçalho. URLs do Hermes/personalizado são validadas: `http` só é aceito em localhost/rede local; endereços de metadados (169.254.x.x) são recusados. Precedência: `HERMES_BASE_URL` → `JARBAS_HERMES_BASE_URL`; `JARBAS_HERMES_MODEL` → `HERMES_MODEL` → `hermes`; `HERMES_API_KEY` → `JARBAS_HERMES_API_KEY` → `JARBAS_CUSTOM_API_KEY`.

Falhas transitórias (5xx e timeout) rendem **uma** repetição curta no mesmo provedor; 401/402/403/404/429 não são repetidos e caem para o próximo. O painel mostra `via provedor · modelo · ms` e, nos erros, um resumo sanitizado das tentativas. Os evals determinísticos do prompt rodam com o resto do pytest (`tests/test_jarbas_evals.py`, marker `eval`).

## Publicar

Em um terminal próprio, na pasta do projeto, rode `.venv/Scripts/python -m scripts.configurar_vercel`. Ele pede a senha e a chave da brapi sem mostrá-las, gera os demais segredos e cadastra tudo em preview. Depois:

1. `npx vercel deploy` cria o preview, para testar.
2. `.venv/Scripts/python -m scripts.configurar_vercel --producao` cadastra também em produção.
3. `npx vercel deploy --prod` publica.

Migrations não rodam sozinhas: `.venv/Scripts/python -m db.migrate`. Para voltar ao deploy anterior: `npx vercel rollback`.

Fontes de mercado e limites: [docs/fontes-de-dados.md](docs/fontes-de-dados.md). O app funciona sem custo com os arquivos oficiais da B3; a chave da brapi é opcional e acrescenta contratos em aberto e eventos.
