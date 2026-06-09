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

3. **Rodar o app web (porta 3000):**

   ```bash
   npm run dev
   ```

4. **Rodar o worker (em outro terminal):**

   ```bash
   npm run dev:worker
   ```

### Scripts (raiz)

| Comando | Descrição |
|---|---|
| `npm run dev` | Next.js dev server (`apps/web`) |
| `npm run dev:worker` | Worker em watch mode (`apps/worker`) |
| `npm run build` | Build de todos os workspaces |
| `npm run typecheck` | `tsc --noEmit` em todos os workspaces |
| `npm run lint` | ESLint em todos os workspaces |

## CI

GitHub Actions roda lint + typecheck + build em cada push/PR para `main`
(`.github/workflows/ci.yml`).

## Fases de construção

1. ~~Fase 0 — Fundação (monorepo, TS, Tailwind, ESLint, CI)~~
2. Fase 1 — Landing (porte do `index.html` aprovado)
3. Fase 2 — Auth + waitlist (Supabase Auth, Google + e-mail, aprovação manual)
4. Fase 3 — App shell (chat de criação de job, lista, detalhe com timeline)
5. Fase 4 — Runtime (worker + pg-boss + Claude)
6. Fase 5 — Entregáveis (PPTX/PDF/DOCX/XLSX + Storage)
7. Fase 6 — Hardening (RLS, rate limit, LGPD, estados de erro)

Dúvidas e bloqueios ficam registrados em [PENDENCIAS.md](./PENDENCIAS.md).
