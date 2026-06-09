import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { PendingList, type PendingProfile } from "./pending-list";

export const metadata: Metadata = {
  title: "Admin — EVA",
};

export default async function AdminPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: me } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();
  if (me?.role !== "admin") redirect("/app");

  const { data: pending } = await supabase
    .from("profiles")
    .select("id, email, full_name, company, status, created_at")
    .eq("status", "pending")
    .order("created_at", { ascending: true });

  const { data: decided } = await supabase
    .from("profiles")
    .select("id, email, full_name, company, status, created_at")
    .neq("status", "pending")
    .order("created_at", { ascending: false })
    .limit(50);

  return (
    <div className="mx-auto max-w-4xl px-8 py-12">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-eva-tertiary">
        Administração
      </p>
      <h1 className="text-3xl font-bold tracking-tight text-eva-text">
        Lista de espera
      </h1>
      <p className="mt-2 text-sm text-eva-secondary">
        Aprove ou rejeite contas pendentes. Aprovados ganham acesso imediato a /app.
      </p>

      <section className="mt-10">
        <h2 className="mb-4 text-lg font-semibold text-eva-text">
          Pendentes ({pending?.length ?? 0})
        </h2>
        <PendingList profiles={(pending ?? []) as PendingProfile[]} mode="pending" />
      </section>

      <section className="mt-12">
        <h2 className="mb-4 text-lg font-semibold text-eva-text">Decididos</h2>
        <PendingList profiles={(decided ?? []) as PendingProfile[]} mode="decided" />
      </section>
    </div>
  );
}
