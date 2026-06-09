import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { PendingList, type PendingProfile } from "./pending-list";
import {
  JOB_STATUS_CLASSES,
  JOB_STATUS_LABEL,
  formatDate,
  type JobRow,
} from "@/lib/types";

type AdminJobRow = Pick<JobRow, "id" | "title" | "status" | "created_at"> & {
  profiles: { email: string } | null;
};

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

  const { data: jobs } = await supabase
    .from("jobs")
    .select("id, title, status, created_at, profiles ( email )")
    .order("created_at", { ascending: false })
    .limit(100);

  const adminJobs = (jobs ?? []) as unknown as AdminJobRow[];

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

      <section className="mt-12">
        <h2 className="mb-4 text-lg font-semibold text-eva-text">
          Todos os jobs ({adminJobs.length})
        </h2>
        {adminJobs.length === 0 ? (
          <p className="rounded-eva border border-eva-border bg-eva-bg-alt px-4 py-6 text-center text-sm text-eva-tertiary">
            Nenhum job criado ainda.
          </p>
        ) : (
          <div className="overflow-hidden rounded-eva border border-eva-border">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-eva-border bg-eva-bg-alt text-xs text-eva-secondary">
                <tr>
                  <th className="px-4 py-3 font-semibold">Título</th>
                  <th className="px-4 py-3 font-semibold">Usuário</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Criado em</th>
                </tr>
              </thead>
              <tbody>
                {adminJobs.map((job) => (
                  <tr
                    key={job.id}
                    className="border-b border-eva-border last:border-b-0"
                  >
                    <td className="px-4 py-3 font-medium text-eva-text">{job.title}</td>
                    <td className="px-4 py-3 text-eva-secondary">
                      {job.profiles?.email ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${JOB_STATUS_CLASSES[job.status]}`}
                      >
                        {JOB_STATUS_LABEL[job.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-eva-secondary">
                      {formatDate(job.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
