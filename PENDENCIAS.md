# Pendências

Registro de dúvidas, bloqueios e justificativas, conforme regras 1 e 7 do spec.

## Resolvidos

1. ~~`index.html` da landing aprovada não está no repositório.~~
   **Resolvido na Fase 1:** o usuário forneceu o arquivo em
   `~/EVA LANDING PAGE/index.html`; portado para
   `apps/web/app/(marketing)/page.tsx` com CSS escopado em `landing.css`.

2. ~~Assets da landing ausentes.~~
   **Resolvido na Fase 1:** `logo-eva-black.png` e `hero-product.png` copiados
   da pasta da landing para `apps/web/public/assets/`.

## Avisos operacionais

3. **Deploy Railway do app legado:** o app Python/FastAPI foi movido para
   `legacy/`. O deploy do Railway que apontava para `Procfile` na raiz vai
   quebrar no próximo push. Opções: (a) apontar o Root Directory do serviço
   Railway para `legacy/`, ou (b) desativar o serviço se o app antigo for
   descontinuado.

4. **Setup do Supabase pendente (operação manual):** para o fluxo completo
   funcionar é preciso (a) criar o projeto no Supabase, (b) rodar as
   migrations `0001`–`0003` no SQL Editor, (c) habilitar o provider Google
   em Authentication, (d) preencher o `.env` e (e) rodar `npm run seed:admin`
   após criar a conta do admin. Passo a passo no README.

5. **Puppeteer no deploy do worker:** o download do Chromium acontece no
   `npm install`. Em ambientes slim (Railway/Render), garanta as libs de
   sistema do Chrome ou use buildpack/nixpacks com `chromium`. Flags
   `--no-sandbox` já configuradas no código para containers.

6. **Verificação funcional ponta a ponta pendente:** todas as fases passaram
   em build/lint/typecheck/testes, mas o critério "criar conta → aprovar →
   job → download" exige um projeto Supabase real + chave Anthropic. Assim
   que o `.env` estiver preenchido, validar o fluxo completo.

## Justificativas de dependências fora da lista da seção 2

0. **`@supabase/ssr` (apps/web):** pacote oficial do Supabase para auth
   cookie-based no Next.js App Router (Server Components + middleware).
   É a forma recomendada pela própria Supabase de usar o item "Supabase
   (Auth)" da seção 2 com Next.js 15.

4. **`tsx` (apps/worker):** runner TypeScript para o worker Node em dev e
   produção, evitando etapa de bundling no MVP. Não altera a stack — o worker
   continua "App Node.js + TypeScript" conforme a seção 2.
5. **`@eslint/eslintrc` (apps/web):** ponte de compatibilidade exigida pelo
   `eslint-config-next` com ESLint 9 flat config. Parte do toolchain padrão
   do Next.js 15, não uma biblioteca de runtime.
