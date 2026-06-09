import { loadServerEnv } from "@eva/shared";

/**
 * Worker da EVA — consome a fila `eva-jobs` via pg-boss.
 * Fase 0: apenas valida o ambiente no boot e mantém o processo vivo.
 * A integração pg-boss + Claude chega na Fase 4.
 */
function main(): void {
  const env = loadServerEnv();

  console.log("[eva-worker] ambiente validado com sucesso");
  console.log(`[eva-worker] modelo configurado: ${env.ANTHROPIC_MODEL}`);
  console.log("[eva-worker] fila pg-boss será conectada na Fase 4 — encerrando.");
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
