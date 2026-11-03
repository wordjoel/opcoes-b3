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
npm run build
```

## Publicar

Cadastre as variáveis de `.env.example` no projeto da Vercel, exceto `B3_INSECURE_COOKIE`, e rode `db.migrate` apontando para o Turso antes do deploy.
