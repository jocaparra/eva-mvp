import type { DeliverableTipo, JobStatus, MessageRole } from "@eva/shared";

/** Linhas das tabelas como retornadas pelo Supabase (snake_case). */

export type JobRow = {
  id: string;
  user_id: string;
  title: string;
  prompt: string;
  status: JobStatus;
  plan: unknown;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type JobStepRow = {
  id: string;
  job_id: string;
  ordem: number;
  descricao: string;
  status: "queued" | "running" | "done" | "failed";
  output: unknown;
  started_at: string | null;
  finished_at: string | null;
};

export type DeliverableRow = {
  id: string;
  job_id: string;
  tipo: DeliverableTipo;
  filename: string;
  storage_path: string;
  size_bytes: number | null;
  created_at: string;
};

export type MessageRow = {
  id: string;
  job_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
};

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  queued: "Na fila",
  planning: "Planejando",
  running: "Executando",
  delivered: "Entregue",
  failed: "Falhou",
  cancelled: "Cancelado",
};

export const JOB_STATUS_CLASSES: Record<JobStatus, string> = {
  queued: "border border-eva-border bg-eva-bg-alt text-eva-secondary",
  planning: "border border-eva-border bg-white text-eva-text",
  running: "bg-eva-dark text-white",
  delivered: "border border-green-200 bg-green-50 text-green-700",
  failed: "border border-red-200 bg-red-50 text-red-700",
  cancelled: "border border-eva-border bg-eva-bg-alt text-eva-tertiary",
};

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(job: Pick<JobRow, "started_at" | "finished_at">): string {
  if (!job.started_at) return "—";
  const end = job.finished_at ? new Date(job.finished_at) : new Date();
  const seconds = Math.max(0, Math.round((end.getTime() - new Date(job.started_at).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}min ${seconds % 60}s`;
}
