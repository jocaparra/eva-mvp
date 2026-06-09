import type Anthropic from "@anthropic-ai/sdk";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { WorkerEnv } from "./lib/env";
import { planJob } from "./planner";
import { executeSteps } from "./executor";

type JobRecord = {
  id: string;
  user_id: string;
  title: string;
  prompt: string;
  status: string;
};

/**
 * Orquestra um job de ponta a ponta: planning → running → delivered.
 * Erros nunca derrubam o processo: são persistidos em jobs.error (pt-BR)
 * e o job é marcado como failed.
 */
export async function runJob(params: {
  client: Anthropic;
  env: WorkerEnv;
  supabase: SupabaseClient;
  jobId: string;
}): Promise<void> {
  const { client, env, supabase, jobId } = params;

  const { data: job } = await supabase
    .from("jobs")
    .select("id, user_id, title, prompt, status")
    .eq("id", jobId)
    .maybeSingle<JobRecord>();

  if (!job) {
    console.error(`[runner] job ${jobId} não encontrado — ignorando.`);
    return;
  }
  if (job.status === "cancelled") {
    console.log(`[runner] job ${jobId} cancelado — ignorando.`);
    return;
  }

  try {
    // ── Planejamento ──
    await supabase
      .from("jobs")
      .update({ status: "planning", started_at: new Date().toISOString() })
      .eq("id", jobId);

    const plan = await planJob({ client, env, supabase, jobId, prompt: job.prompt });

    await supabase.from("messages").insert({
      job_id: jobId,
      role: "eva",
      content: `Plano definido: ${plan.steps.length} etapas. Iniciando execução.`,
    });

    // ── Execução sequencial ──
    await supabase.from("jobs").update({ status: "running" }).eq("id", jobId);

    const outputs = await executeSteps({
      client,
      env,
      supabase,
      jobId,
      objetivo: job.prompt,
      plan,
    });

    // ── Entrega ──
    // A geração de documento (PPTX/PDF/DOCX/XLSX) + upload no Storage chega
    // na Fase 5. Aqui o conteúdo final já está em job_steps.output.
    const finalStep = outputs[outputs.length - 1];
    await supabase.from("messages").insert({
      job_id: jobId,
      role: "eva",
      content: finalStep
        ? `Execução concluída. Resultado final:\n\n${finalStep.content.slice(0, 4000)}`
        : "Execução concluída.",
    });

    await supabase
      .from("jobs")
      .update({ status: "delivered", finished_at: new Date().toISOString() })
      .eq("id", jobId);

    console.log(`[runner] job ${jobId} entregue.`);
  } catch (error) {
    const motivo =
      error instanceof Error ? error.message : "Erro desconhecido durante a execução.";
    console.error(`[runner] job ${jobId} falhou: ${motivo}`);

    await supabase
      .from("jobs")
      .update({
        status: "failed",
        error: motivo,
        finished_at: new Date().toISOString(),
      })
      .eq("id", jobId);

    await supabase.from("messages").insert({
      job_id: jobId,
      role: "system",
      content: `A execução falhou: ${motivo}`,
    });
  }
}
