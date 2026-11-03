# B3 Opções Pro

Análise de opções da B3 para uso pessoal. Só análise: não existe envio de ordens.

- `src/`: PWA em React
- `api/index.py` e `app/`: API em FastAPI, com login
- `core/`, `data/`, `quant/`: contratos, fonte de dados e motor quantitativo
- `db/`: cliente Turso/SQLite e migrations

Convenções e limitações: `docs/quant-convencoes.md`.

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

## Publicar

Em um terminal próprio, na pasta do projeto, rode `.venv/Scripts/python -m scripts.configurar_vercel`. Ele pede a senha e a chave da brapi sem mostrá-las, gera os demais segredos e cadastra tudo em preview. Depois:

1. `npx vercel deploy` cria o preview, para testar.
2. `.venv/Scripts/python -m scripts.configurar_vercel --producao` cadastra também em produção.
3. `npx vercel deploy --prod` publica.

Migrations não rodam sozinhas: `.venv/Scripts/python -m db.migrate`. Para voltar ao deploy anterior: `npx vercel rollback`.

Fontes de mercado e limites: [docs/fontes-de-dados.md](docs/fontes-de-dados.md). O app funciona sem custo com os arquivos oficiais da B3; a chave da brapi é opcional e acrescenta contratos em aberto e eventos.
