import { PgBoss } from "pg-boss";

export const QUEUE_NAME = "eva-jobs";

/**
 * Singleton do pg-boss para enqueue em route handlers.
 * Guardado em globalThis para sobreviver ao hot reload em dev.
 * Só roda server-side (DATABASE_URL nunca chega ao client).
 */
const globalForBoss = globalThis as unknown as {
  evaBossPromise: Promise<PgBoss> | undefined;
};

async function startBoss(): Promise<PgBoss> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "DATABASE_URL é obrigatória para enfileirar jobs. Confira o .env.example.",
    );
  }
  const boss = new PgBoss({ connectionString });
  boss.on("error", (error: unknown) => {
    console.error("[pg-boss]", error instanceof Error ? error.message : error);
  });
  await boss.start();
  try {
    await boss.createQueue(QUEUE_NAME);
  } catch {
    // Fila já criada pelo worker — seguir normalmente.
  }
  return boss;
}

async function getBoss(): Promise<PgBoss> {
  if (!globalForBoss.evaBossPromise) {
    globalForBoss.evaBossPromise = startBoss().catch((error) => {
      // Permite nova tentativa no próximo request em vez de cachear a falha.
      globalForBoss.evaBossPromise = undefined;
      throw error;
    });
  }
  return globalForBoss.evaBossPromise;
}

/** Enfileira a execução de um job criado na web. */
export async function enqueueJob(jobId: string): Promise<void> {
  const boss = await getBoss();
  await boss.send(QUEUE_NAME, { jobId });
}
