import { PgBoss, type Job } from "pg-boss";
import { z } from "zod";
import { loadWorkerEnv } from "./lib/env";
import { createWorkerSupabase } from "./lib/supabase";
import { createAnthropicClient } from "./lib/claude";
import { runJob } from "./runner";

export const QUEUE_NAME = "eva-jobs";

const jobPayloadSchema = z.object({
  jobId: z.uuid(),
});

/**
 * Worker da EVA — consome a fila `eva-jobs` via pg-boss.
 * Jobs órfãos (worker reiniciado) voltam para a fila automaticamente:
 * o pg-boss garante isso via expiração, não reimplementamos.
 */
async function main(): Promise<void> {
  const env = loadWorkerEnv();
  const supabase = createWorkerSupabase(env);
  const anthropic = createAnthropicClient(env);

  const boss = new PgBoss({ connectionString: env.DATABASE_URL });

  boss.on("error", (error: unknown) => {
    // Erros internos do pg-boss não podem derrubar o processo.
    console.error("[pg-boss]", error instanceof Error ? error.message : error);
  });

  await boss.start();
  // Expiração maior que o pior caso (6 steps × 10 min) para não matar jobs
  // longos legítimos; órfãos voltam para a fila via pg-boss.
  await boss.createQueue(QUEUE_NAME, { expireInSeconds: 70 * 60 });

  await boss.work(QUEUE_NAME, { batchSize: 1 }, async (jobs: Job<unknown>[]) => {
    for (const job of jobs) {
      const parsed = jobPayloadSchema.safeParse(job.data);
      if (!parsed.success) {
        console.error(`[worker] payload inválido no job ${job.id} — descartando.`);
        continue;
      }
      console.log(`[worker] executando job ${parsed.data.jobId}`);
      await runJob({
        client: anthropic,
        env,
        supabase,
        jobId: parsed.data.jobId,
      });
    }
  });

  console.log(`[worker] conectado — aguardando jobs na fila "${QUEUE_NAME}".`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
