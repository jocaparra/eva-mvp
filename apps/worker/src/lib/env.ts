import { z } from "zod";
import { loadServerEnv, type ServerEnv } from "@eva/shared";

const workerExtraSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z.url(
    "NEXT_PUBLIC_SUPABASE_URL deve ser uma URL válida do Supabase",
  ),
});

export type WorkerEnv = ServerEnv & z.infer<typeof workerExtraSchema>;

/** Valida todo o ambiente do worker no boot — falha com mensagem clara. */
export function loadWorkerEnv(): WorkerEnv {
  const server = loadServerEnv();
  const parsed = workerExtraSchema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  - ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    throw new Error(
      `Variáveis de ambiente inválidas ou ausentes:\n${issues}\nConfira o .env.example.`,
    );
  }
  return { ...server, ...parsed.data };
}
