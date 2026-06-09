/**
 * Acesso às env vars públicas do Supabase no app web.
 * Referências literais a process.env.NEXT_PUBLIC_* são obrigatórias para o
 * Next.js inlinar os valores no bundle do client.
 */
export function getPublicSupabaseEnv(): { url: string; anonKey: string } {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_ANON_KEY são obrigatórias. Confira o .env.example.",
    );
  }
  return { url, anonKey };
}
