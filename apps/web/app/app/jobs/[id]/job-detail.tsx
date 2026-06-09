"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import {
  JOB_STATUS_CLASSES,
  JOB_STATUS_LABEL,
  formatDate,
  formatDuration,
  type DeliverableRow,
  type JobRow,
  type JobStepRow,
  type MessageRow,
} from "@/lib/types";

const POLL_INTERVAL_MS = 5000;
const ACTIVE_STATUSES = new Set(["queued", "planning", "running"]);

const STEP_STATUS_ICON: Record<JobStepRow["status"], string> = {
  queued: "○",
  running: "◐",
  done: "●",
  failed: "✕",
};

const TIPO_LABEL: Record<DeliverableRow["tipo"], string> = {
  pptx: "PowerPoint",
  pdf: "PDF",
  docx: "Word",
  xlsx: "Excel",
};

export function JobDetail({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobRow | null>(null);
  const [steps, setSteps] = useState<JobStepRow[]>([]);
  const [messages, setMessages] = useState<MessageRow[]>([]);
  const [deliverables, setDeliverables] = useState<DeliverableRow[]>([]);
  const [notFound, setNotFound] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    const supabase = createClient();
    const [jobRes, stepsRes, messagesRes, deliverablesRes] = await Promise.all([
      supabase.from("jobs").select("*").eq("id", jobId).maybeSingle(),
      supabase.from("job_steps").select("*").eq("job_id", jobId).order("ordem"),
      supabase.from("messages").select("*").eq("job_id", jobId).order("created_at"),
      supabase.from("deliverables").select("*").eq("job_id", jobId).order("created_at"),
    ]);

    if (!jobRes.data) {
      setNotFound(true);
      return;
    }
    setJob(jobRes.data as JobRow);
    setSteps((stepsRes.data ?? []) as JobStepRow[]);
    setMessages((messagesRes.data ?? []) as MessageRow[]);
    setDeliverables((deliverablesRes.data ?? []) as DeliverableRow[]);
  }, [jobId]);

  useEffect(() => {
    void fetchAll();
    const interval = setInterval(() => void fetchAll(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchAll]);

  async function handleDownload(deliverableId: string) {
    setDownloadError(null);
    try {
      const response = await fetch(`/api/deliverables/${deliverableId}/url`);
      const body = (await response.json()) as { url?: string; error?: string };
      if (!response.ok || !body.url) {
        setDownloadError(body.error ?? "Não foi possível gerar o link de download.");
        return;
      }
      window.open(body.url, "_blank", "noopener,noreferrer");
    } catch {
      setDownloadError("Falha de conexão ao gerar o link de download.");
    }
  }

  if (notFound) {
    return (
      <div className="rounded-eva border border-eva-border bg-eva-bg-alt px-4 py-10 text-center">
        <p className="text-sm font-medium text-eva-text">Job não encontrado.</p>
        <Link href="/app/jobs" className="mt-2 inline-block text-sm text-eva-secondary underline">
          Voltar para a lista
        </Link>
      </div>
    );
  }

  if (!job) {
    return (
      <p className="rounded-eva border border-eva-border bg-eva-bg-alt px-4 py-8 text-center text-sm text-eva-tertiary">
        Carregando job...
      </p>
    );
  }

  return (
    <div>
      <Link href="/app/jobs" className="text-xs text-eva-tertiary hover:text-eva-text">
        ← Jobs
      </Link>

      <div className="mt-3 flex items-start justify-between gap-4">
        <h1 className="text-2xl font-bold leading-snug tracking-tight text-eva-text">
          {job.title}
        </h1>
        <span
          className={`mt-1 inline-block shrink-0 rounded-full px-3 py-1 text-xs font-medium ${JOB_STATUS_CLASSES[job.status]}`}
        >
          {JOB_STATUS_LABEL[job.status]}
        </span>
      </div>
      <p className="mt-1 text-xs text-eva-tertiary">
        Criado em {formatDate(job.created_at)} · Duração {formatDuration(job)}
      </p>

      {job.error ? (
        <p className="mt-4 rounded-eva border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {job.error}
        </p>
      ) : null}

      {/* ── Timeline ── */}
      <section className="mt-10">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-eva-secondary">
          Execução
        </h2>
        {steps.length === 0 ? (
          <p className="rounded-eva border border-eva-border bg-eva-bg-alt px-4 py-6 text-sm text-eva-tertiary">
            {ACTIVE_STATUSES.has(job.status)
              ? "Aguardando o planejamento da EVA..."
              : "Nenhuma etapa registrada."}
          </p>
        ) : (
          <ol className="flex flex-col">
            {steps.map((step, index) => (
              <li key={step.id} className="relative flex gap-4 pb-6 last:pb-0">
                {index < steps.length - 1 ? (
                  <span className="absolute left-[9px] top-6 h-full w-px bg-eva-border" />
                ) : null}
                <span
                  className={`z-10 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] ${
                    step.status === "done"
                      ? "bg-eva-dark text-white"
                      : step.status === "running"
                        ? "border border-eva-text bg-white text-eva-text"
                        : step.status === "failed"
                          ? "bg-red-600 text-white"
                          : "border border-eva-border bg-white text-eva-tertiary"
                  }`}
                >
                  {STEP_STATUS_ICON[step.status]}
                </span>
                <div className="min-w-0">
                  <p
                    className={`text-sm ${
                      step.status === "queued" ? "text-eva-tertiary" : "text-eva-text"
                    }`}
                  >
                    {step.descricao}
                  </p>
                  {step.started_at ? (
                    <p className="mt-0.5 text-xs text-eva-tertiary">
                      {step.status === "done" && step.finished_at
                        ? `Concluído em ${formatDate(step.finished_at)}`
                        : step.status === "running"
                          ? "Executando..."
                          : step.status === "failed"
                            ? "Falhou"
                            : ""}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* ── Mensagens da EVA ── */}
      {messages.length > 0 ? (
        <section className="mt-10">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-eva-secondary">
            Mensagens
          </h2>
          <div className="flex flex-col gap-3">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`max-w-[85%] rounded-eva border px-4 py-3 text-sm leading-relaxed ${
                  message.role === "user"
                    ? "self-end border-eva-border bg-eva-bg-alt text-eva-text"
                    : "self-start border-eva-border bg-white text-eva-text"
                }`}
              >
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-eva-tertiary">
                  {message.role === "user" ? "Você" : message.role === "eva" ? "EVA" : "Sistema"}
                </p>
                {message.content}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {/* ── Entregáveis ── */}
      {deliverables.length > 0 ? (
        <section className="mt-10">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-eva-secondary">
            Entregáveis
          </h2>
          {downloadError ? (
            <p className="mb-3 rounded-eva border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
              {downloadError}
            </p>
          ) : null}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {deliverables.map((deliverable) => (
              <div
                key={deliverable.id}
                className="flex items-center justify-between gap-3 rounded-eva border border-eva-border bg-white px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-eva-text">
                    {deliverable.filename}
                  </p>
                  <p className="text-xs text-eva-tertiary">
                    {TIPO_LABEL[deliverable.tipo]}
                    {deliverable.size_bytes
                      ? ` · ${Math.max(1, Math.round(deliverable.size_bytes / 1024))} KB`
                      : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDownload(deliverable.id)}
                  className="shrink-0 rounded-eva bg-eva-dark px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-[#1E293B]"
                >
                  Baixar
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
