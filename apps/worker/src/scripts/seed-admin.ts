import { createClient } from "@supabase/supabase-js";
import { z } from "zod";

/**
 * Seed: promove o e-mail definido em ADMIN_EMAIL a admin (role=admin,
 * status=approved). O usuário precisa já ter criado a conta.
 *
 * Uso: npm run seed:admin (na raiz; lê .env da raiz se existir)
 */
const envSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z.url("NEXT_PUBLIC_SUPABASE_URL deve ser uma URL válida"),
  SUPABASE_SERVICE_ROLE_KEY: z.string().min(1, "SUPABASE_SERVICE_ROLE_KEY é obrigatória"),
  ADMIN_EMAIL: z.email("ADMIN_EMAIL deve ser um e-mail válido"),
});

async function main(): Promise<void> {
  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  - ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    throw new Error(`Variáveis de ambiente inválidas ou ausentes:\n${issues}`);
  }
  const env = parsed.data;

  const supabase = createClient(
    env.NEXT_PUBLIC_SUPABASE_URL,
    env.SUPABASE_SERVICE_ROLE_KEY,
    { auth: { persistSession: false } },
  );

  const { data: profile, error: findError } = await supabase
    .from("profiles")
    .select("id, email, role, status")
    .eq("email", env.ADMIN_EMAIL)
    .maybeSingle();

  if (findError) {
    throw new Error(`Erro ao buscar perfil: ${findError.message}`);
  }
  if (!profile) {
    throw new Error(
      `Nenhum perfil encontrado para ${env.ADMIN_EMAIL}. ` +
        "Crie a conta primeiro (signup) e rode o seed de novo.",
    );
  }

  const { error: updateError } = await supabase
    .from("profiles")
    .update({ role: "admin", status: "approved" })
    .eq("id", profile.id);

  if (updateError) {
    throw new Error(`Erro ao promover admin: ${updateError.message}`);
  }

  console.log(`[seed-admin] ${env.ADMIN_EMAIL} promovido a admin e aprovado.`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
