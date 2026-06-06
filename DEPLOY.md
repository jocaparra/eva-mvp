# Deploy EVA no Railway

App já configurado em `https://eva-mvp-production.up.railway.app` (ver `BASE_URL` no `.env`).

## Pré-requisitos

1. **Código no GitHub** — commit + push do `main` com as etapas 1–7
2. **Postgres com pgvector** — recomendado: **Supabase → Database → Connection string (URI)**  
   Use o pooler (`:6543`) ou conexão direta (`:5432`). O app normaliza `postgres://` → `postgresql+psycopg2://` automaticamente.
3. **JWT** — gere um segredo forte (`openssl rand -hex 32`)

## Variáveis no Railway (service web)

### Obrigatórias

| Variável | Exemplo / notas |
|----------|-----------------|
| `DATABASE_URL` | `postgresql://postgres.[ref]:[pwd]@...supabase.com:6543/postgres` |
| `JWT_SECRET_KEY` | string aleatória 32+ chars |
| `GOOGLE_API_KEY` | Gemini |
| `TAVILY_API_KEY` | pesquisa web |
| `BASE_URL` | `https://eva-mvp-production.up.railway.app` |
| `PRESENTON_API_KEY` | geração PPT (ou template local) |

### Recomendadas

| Variável | Valor sugerido |
|----------|----------------|
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` |
| `WHATSAPP_OPEN_ACCESS` | `false` em prod (ou lista em `WHATSAPP_ALLOWED_PHONES`) |

### Persistência de arquivos (escolha uma)

**Opção A — Volume Railway (simples)**

1. No service → **Volumes** → mount em `/data`
2. Variáveis:
   ```
   ARTIFACT_STORAGE=local
   ARTIFACT_STORAGE_LOCAL_PATH=/data/artifact_storage
   DEAL_UPLOAD_PATH=/data/uploads/deal_workspace
   ```

**Opção B — Supabase Storage (sobrevive redeploy sem volume)**

1. Crie bucket `artefatos` no Supabase Storage (público ou policies conforme sua conta)
2. Variáveis:
   ```
   ARTIFACT_STORAGE=supabase
   ARTIFACT_STORAGE_SUPABASE_BUCKET=artefatos
   SUPABASE_URL=...
   SUPABASE_KEY=...   # service role ou anon conforme policies
   ```

### Opcionais (WhatsApp / billing / arquivos legado)

- `ZAPI_*` — webhook WhatsApp
- `SUPABASE_URL` + `SUPABASE_KEY` — painel **Arquivos** (`/files`); **não** é o banco de deals
- `STRIPE_*` — se usar checkout

## O que o deploy executa

O `Procfile` chama `scripts/start.sh`:

1. `alembic upgrade head` (migrations 001–005, inclui `generation_jobs`)
2. `uvicorn app.main:app` na porta `$PORT`

Healthcheck Railway: **`GET /health`** → `{"status":"ok"}`

## Checklist pós-deploy

```bash
# 1. Health
curl https://eva-mvp-production.up.railway.app/health

# 2. Login dev (desabilitar em prod público ou proteger)
curl -X POST https://eva-mvp-production.up.railway.app/auth/dev-login \
  -H "Content-Type: application/json" \
  -d '{"phone":"5511999999999"}'

# 3. Deals sem Supabase (só DATABASE_URL)
curl https://eva-mvp-production.up.railway.app/deals \
  -H "Authorization: Bearer $TOKEN"
# → 200 (lista), nunca 503

# 4. Migrations aplicadas (no log do deploy)
# "Alembic upgrade head" sem erro
```

## Primeiro deploy com banco novo

1. Defina `DATABASE_URL` no Railway
2. Redeploy — o `start.sh` roda `alembic upgrade head`
3. Confirme extensão `vector` (migration 002) — Supabase já suporta; Railway Postgres vanilla pode exigir imagem com pgvector

## Atualizar produção (fluxo habitual)

```bash
git add -A
git commit -m "feat: unificar banco SQLAlchemy, storage, UI revisão"
git push origin main
```

Railway redeploy automático se CI/CD ligado ao repo.

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| 503 `JWT_SECRET_KEY não configurada` | falta env | definir `JWT_SECRET_KEY` |
| Login OK, deals 500 | migrations | ver logs `alembic upgrade head` |
| Upload PDF OK, RAG vazio | pgvector / embeddings | checar `GOOGLE_API_KEY`, logs ingestão |
| Download 404 após redeploy | disco efêmero | volume `/data` ou `ARTIFACT_STORAGE=supabase` |
| `postgres://` driver error | URL antiga | já normalizado em `app/database.py` |

## Smoke test local antes do push

```bash
pytest tests/test_e2e_smoke_stage7.py -v
pytest tests/ -q
```
