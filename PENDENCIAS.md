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

## Justificativas de dependências fora da lista da seção 2

4. **`tsx` (apps/worker):** runner TypeScript para o worker Node em dev e
   produção, evitando etapa de bundling no MVP. Não altera a stack — o worker
   continua "App Node.js + TypeScript" conforme a seção 2.
5. **`@eslint/eslintrc` (apps/web):** ponte de compatibilidade exigida pelo
   `eslint-config-next` com ESLint 9 flat config. Parte do toolchain padrão
   do Next.js 15, não uma biblioteca de runtime.
