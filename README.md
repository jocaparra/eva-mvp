# EVA

**Building Intelligence for the Real Economy.**
The Operating System for Modern Businesses.

EVA é um runtime operacional assíncrono que executa workflows completos de
análise, documentação e decisão. O usuário envia um objetivo ("Crie um CIM da
empresa XPTO"), a EVA planeja, divide em subtarefas, executa e entrega
documentos institucionais prontos (PPTX, PDF, DOCX, XLSX).

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend + API | Next.js 15 (App Router) + TypeScript estrito + Tailwind CSS |
| Auth, banco, storage | Supabase (Auth + Postgres + Storage) |
| Fila de jobs | pg-boss (fila sobre o próprio Postgres) |
| Worker assíncrono | Node.js + TypeScript (`apps/worker`) |
| LLM | Anthropic Claude API (`@anthropic-ai/sdk`) |
| Documentos | pptxgenjs, docx, exceljs, Puppeteer (PDF) |
| Deploy | Vercel (web) + Railway/Render (worker) |

## Estrutura do monorepo

```
eva-mvp/
├── apps/
│   ├── web/        # Next.js 15 — landing, auth, app, admin
│   └── worker/     # Worker Node — consome fila pg-boss, executa jobs
├── packages/
│   └── shared/     # Tipos, schemas zod, validação de env, cliente Supabase
├── supabase/
│   └── migrations/ # Migrations SQL versionadas (a partir da Fase 2)
└── legacy/         # App Python/FastAPI anterior (referência, não usado)
```

## Setup local

### Pré-requisitos

- Node.js ≥ 24 (há `.nvmrc` na raiz — use `nvm use`)
- Conta no [Supabase](https://supabase.com) com projeto criado
- Chave da [Anthropic](https://console.anthropic.com)

### Passo a passo

1. **Clonar e instalar dependências:**

   ```bash
   git clone https://github.com/jocaparra/eva-mvp.git
   cd eva-mvp
   npm install
   ```

2. **Configurar variáveis de ambiente:**

   ```bash
   cp .env.example .env
   ```

   Preencha cada chave — o `.env.example` indica onde obter cada uma.
   As env vars são validadas com zod no boot; se faltar alguma, o processo
   falha com mensagem clara apontando o que está ausente.

3. **Aplicar as migrations no Supabase:**

   No painel do Supabase (SQL Editor), execute os arquivos de
   `supabase/migrations/` em ordem (`0001`, `0002`, `0003`). Eles criam
   `profiles` (com trigger de signup), `jobs`/`job_steps`/`deliverables`/
   `messages`, toda a RLS e o bucket privado `deliverables`.

4. **Habilitar o login Google (opcional, recomendado):**

   Supabase → Authentication → Providers → Google. Configure o OAuth Client
   no Google Cloud Console com redirect
   `https://SEU-PROJETO.supabase.co/auth/v1/callback`.

5. **Rodar o app web (porta 3000):**

   ```bash
   npm run dev
   ```

6. **Rodar o worker (em outro terminal):**

   ```bash
   npm run dev:worker
   ```

7. **Promover o admin (depois de criar a conta via signup):**

   ```bash
   npm run seed:admin
   ```

   Promove o e-mail definido em `ADMIN_EMAIL` a admin com acesso aprovado.

### Scripts (raiz)

| Comando | Descrição |
|---|---|
| `npm run dev` | Next.js dev server (`apps/web`) |
| `npm run dev:worker` | Worker em watch mode (`apps/worker`) |
| `npm run build` | Build de todos os workspaces |
| `npm run typecheck` | `tsc --noEmit` em todos os workspaces |
| `npm run lint` | ESLint em todos os workspaces |
| `npm test` | Testes unitários (planner + geradores de documento) |
| `npm run seed:admin` | Promove `ADMIN_EMAIL` a admin aprovado |

## Segurança

- **RLS em duas camadas:** o middleware do Next gate-keia as rotas, mas a
  fonte de verdade é a RLS no Postgres — usuário só lê/escreve as próprias
  linhas; admin lê tudo via função `is_admin()` (security definer).
- **Service role nunca no client:** usada apenas no worker e em route
  handlers (`lib/supabase/admin.ts` tem guarda de runtime).
- **Storage privado:** entregáveis em bucket sem acesso público; download
  somente por URL assinada com expiração de 1 hora.
- **Rate limit:** máximo de 10 jobs por usuário por hora.
- **LGPD:** política de privacidade em `/privacidade`, linkada no footer.

## Deploy

- **Web (Vercel):** Root Directory `apps/web`. Configure as env vars do
  `.env.example` (exceto `ANTHROPIC_*`, que são só do worker).
- **Worker (Railway/Render):** comando `npm start -w apps/worker` com todas
  as env vars do `.env.example`. O Puppeteer baixa o Chromium no
  `npm install`; em imagens slim, instale as dependências de sistema do
  Chrome (no Railway, use a imagem com `nixpacks` padrão Node + pacote
  `chromium`).

## CI

GitHub Actions roda lint + typecheck + testes + build em cada push/PR para
`main` (`.github/workflows/ci.yml`).

## Fases de construção

1. ~~Fase 0 — Fundação (monorepo, TS, Tailwind, ESLint, CI)~~
2. ~~Fase 1 — Landing (porte do `index.html` aprovado)~~
3. ~~Fase 2 — Auth + waitlist (Supabase Auth, Google + e-mail, aprovação manual)~~
4. ~~Fase 3 — App shell (chat de criação de job, lista, detalhe com timeline)~~
5. ~~Fase 4 — Runtime (worker + pg-boss + Claude)~~
6. ~~Fase 5 — Entregáveis (PPTX/PDF/DOCX/XLSX + Storage)~~
7. ~~Fase 6 — Hardening (RLS, rate limit, LGPD, estados de erro)~~

Dúvidas e bloqueios ficam registrados em [PENDENCIAS.md](./PENDENCIAS.md).
