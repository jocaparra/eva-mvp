import type { Metadata } from "next";
import { JobsTable } from "./jobs-table";

export const metadata: Metadata = {
  title: "Jobs — EVA",
};

export default function JobsPage() {
  return (
    <main className="mx-auto max-w-5xl px-8 py-12">
      <h1 className="text-2xl font-bold tracking-tight text-eva-text">Jobs</h1>
      <p className="mt-1 text-sm text-eva-secondary">
        Acompanhe a execução. A lista atualiza automaticamente a cada 5 segundos.
      </p>
      <div className="mt-8">
        <JobsTable />
      </div>
    </main>
  );
}
