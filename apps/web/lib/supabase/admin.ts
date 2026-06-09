import { createClient as createSupabaseClient } from "@supabase/supabase-js";

/**
 * Cliente Supabase com service role — ignora RLS.
 * USO RESTRITO a route handlers e server actions. Nunca importar em
 * Client Components: a guarda abaixo derruba qualquer tentativa no browser.
 */
export function createAdminClient() {
  if (typeof window !== "undefined") {
    throw new Error("createAdminClient não pode ser usado no client.");
  }
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórias no servidor. Confira o .env.example.",
    );
  }
  return createSupabaseClient(url, serviceRoleKey, {
    auth: { persistSession: false },
  });
}
