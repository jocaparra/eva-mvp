import { z } from "zod";

/** Status possíveis de um job — espelha o CHECK constraint da tabela `jobs`. */
export const jobStatusSchema = z.enum([
  "queued",
  "planning",
  "running",
  "delivered",
  "failed",
  "cancelled",
]);
export type JobStatus = z.infer<typeof jobStatusSchema>;

/** Status de aprovação do usuário — espelha o CHECK constraint de `profiles`. */
export const profileStatusSchema = z.enum(["pending", "approved", "rejected"]);
export type ProfileStatus = z.infer<typeof profileStatusSchema>;

/** Papéis de usuário. */
export const profileRoleSchema = z.enum(["user", "admin"]);
export type ProfileRole = z.infer<typeof profileRoleSchema>;

/** Tipos de entregável — espelha o CHECK constraint de `deliverables`. */
export const deliverableTipoSchema = z.enum(["pptx", "pdf", "docx", "xlsx"]);
export type DeliverableTipo = z.infer<typeof deliverableTipoSchema>;

/** Papéis de mensagem na thread de um job. */
export const messageRoleSchema = z.enum(["user", "eva", "system"]);
export type MessageRole = z.infer<typeof messageRoleSchema>;

/** Step do plano gerado pelo EVA Planner (persistido em jobs.plan e job_steps). */
export const planStepSchema = z.object({
  ordem: z.number().int().positive(),
  descricao: z.string().min(1),
  tipo_entregavel: deliverableTipoSchema.nullable(),
});
export type PlanStep = z.infer<typeof planStepSchema>;

/** Plano completo retornado pelo EVA Planner. */
export const planSchema = z.object({
  steps: z.array(planStepSchema).min(1),
});
export type Plan = z.infer<typeof planSchema>;
