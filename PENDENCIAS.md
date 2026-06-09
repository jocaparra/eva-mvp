# Pendências

Registro de dúvidas, bloqueios e justificativas, conforme regras 1 e 7 do spec.

## Bloqueios ativos

1. **`index.html` da landing aprovada não está no repositório.**
   O usuário confirmou que vai enviar o arquivo no chat. A Fase 1 (porte para
   `apps/web/app/(marketing)/page.tsx`) fica bloqueada até recebê-lo.
   Enquanto isso, existe um placeholder minimalista com os design tokens.

2. **Assets da landing ausentes:** `public/assets/logo-eva-black.png` e
   `public/assets/hero-product.png` não existem no repo. Serão criados como
   placeholders na Fase 1 se não forem fornecidos (sem quebrar o build).

## Avisos operacionais

3. **Deploy Railway do app legado:** o app Python/FastAPI foi movido para
   `legacy/`. O deploy do Railway que apontava para `Procfile` na raiz vai
   quebrar no próximo push. Opções: (a) apontar o Root Directory do serviço
   Railway para `legacy/`, ou (b) desativar o serviço se o app antigo for
   descontinuado.

## Justificativas de dependências fora da lista da seção 2

4. **`tsx` (apps/worker):** runner TypeScript para o worker Node em dev e
   produção, evitando etapa de bundling no MVP. Não altera a stack — o worker
   continua "App Node.js + TypeScript" conforme a seção 2.
5. **`@eslint/eslintrc` (apps/web):** ponte de compatibilidade exigida pelo
   `eslint-config-next` com ESLint 9 flat config. Parte do toolchain padrão
   do Next.js 15, não uma biblioteca de runtime.
