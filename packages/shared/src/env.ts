import { z } from "zod";

/**
 * Validação de variáveis de ambiente com zod.
 * Regra do projeto: se faltar variável, falhar no boot com mensagem clara —
 * nunca falhar silenciosamente em runtime.
 */

const webPublicSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z.url(
    "NEXT_PUBLIC_SUPABASE_URL deve ser uma URL válida do Supabase",
  ),
  NEXT_PUBLIC_SUPABASE_ANON_KEY: z
    .string()
    .min(1, "NEXT_PUBLIC_SUPABASE_ANON_KEY é obrigatória"),
  NEXT_PUBLIC_APP_URL: z.url(
    "NEXT_PUBLIC_APP_URL deve ser uma URL válida (ex.: http://localhost:3000)",
  ),
});

const serverSchema = z.object({
  SUPABASE_SERVICE_ROLE_KEY: z
    .string()
    .min(1, "SUPABASE_SERVICE_ROLE_KEY é obrigatória (só worker/server-side)"),
  DATABASE_URL: z
    .string()
    .min(1, "DATABASE_URL é obrigatória (connection string Postgres para o pg-boss)"),
  ANTHROPIC_API_KEY: z.string().min(1, "ANTHROPIC_API_KEY é obrigatória"),
  ANTHROPIC_MODEL: z.string().min(1).default("claude-sonnet-4-6"),
  ADMIN_EMAIL: z.email("ADMIN_EMAIL deve ser um e-mail válido"),
});

export type WebPublicEnv = z.infer<typeof webPublicSchema>;
export type ServerEnv = z.infer<typeof serverSchema>;

function formatZodError(error: z.ZodError): string {
  const linhas = error.issues.map(
    (issue) => `  - ${issue.path.join(".")}: ${issue.message}`,
  );
  return [
    "Variáveis de ambiente inválidas ou ausentes:",
    ...linhas,
    "Confira o arquivo .env.example na raiz do repositório.",
  ].join("\n");
}

/** Valida as env vars públicas (client-safe). Lança erro legível se inválidas. */
export function loadWebPublicEnv(source: NodeJS.ProcessEnv = process.env): WebPublicEnv {
  const parsed = webPublicSchema.safeParse(source);
  if (!parsed.success) {
    throw new Error(formatZodError(parsed.error));
  }
  return parsed.data;
}

/** Valida as env vars server-side (worker e route handlers). Nunca usar no client. */
export function loadServerEnv(source: NodeJS.ProcessEnv = process.env): ServerEnv {
  const parsed = serverSchema.safeParse(source);
  if (!parsed.success) {
    throw new Error(formatZodError(parsed.error));
  }
  return parsed.data;
}
