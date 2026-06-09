import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "EVA — Plataforma",
};

/**
 * Placeholder do app interno — o shell completo (chat de criação de job,
 * lista e detalhe) chega na Fase 3.
 */
export default async function AppHomePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("full_name, status")
    .eq("id", user.id)
    .single();

  if (profile?.status !== "approved") redirect("/aguardando");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-3xl font-bold tracking-tight text-eva-text">
        Bem-vindo{profile?.full_name ? `, ${profile.full_name}` : ""}.
      </h1>
      <p className="text-sm text-eva-secondary">
        O que a EVA deve executar? O chat de criação de jobs chega na Fase 3.
      </p>
    </main>
  );
}
