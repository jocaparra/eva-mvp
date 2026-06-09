"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import {
  JOB_STATUS_CLASSES,
  JOB_STATUS_LABEL,
  formatDate,
  formatDuration,
  type JobRow,
} from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

export function JobsTable() {
  const [jobs, setJobs] = useState<JobRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    const supabase = createClient();
    const { data, error: queryError } = await supabase
      .from("jobs")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(100);

    if (queryError) {
      setError("Não foi possível carregar os jobs. Tentando de novo...");
      return;
    }
    setError(null);
    setJobs((data ?? []) as JobRow[]);
  }, []);

  useEffect(() => {
    void fetchJobs();
    const interval = setInterval(() => void fetchJobs(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  if (jobs === null && !error) {
    return (
      <p className="rounded-eva border border-eva-border bg-eva-bg-alt px-4 py-8 text-center text-sm text-eva-tertiary">
        Carregando jobs...
      </p>
    );
  }

  if (jobs !== null && jobs.length === 0) {
    return (
      <div className="rounded-eva border border-eva-border bg-eva-bg-alt px-4 py-10 text-center">
        <p className="text-sm font-medium text-eva-text">Nenhum job ainda.</p>
        <p className="mt-1 text-sm text-eva-secondary">
          Crie o primeiro em{" "}
          <Link href="/app" className="underline">
            Novo job
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-eva border border-eva-border">
      {error ? (
        <p className="border-b border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <table className="w-full text-left text-sm">
        <thead className="border-b border-eva-border bg-eva-bg-alt text-xs text-eva-secondary">
          <tr>
            <th className="px-4 py-3 font-semibold">Título</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Criado em</th>
            <th className="px-4 py-3 font-semibold">Duração</th>
          </tr>
        </thead>
        <tbody>
          {(jobs ?? []).map((job) => (
            <tr
              key={job.id}
              className="border-b border-eva-border transition-colors last:border-b-0 hover:bg-eva-bg-alt"
            >
              <td className="px-4 py-3">
                <Link
                  href={`/app/jobs/${job.id}`}
                  className="font-medium text-eva-text hover:underline"
                >
                  {job.title}
                </Link>
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
              <td className="px-4 py-3 text-eva-secondary">{formatDuration(job)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
