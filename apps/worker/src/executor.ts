import type Anthropic from "@anthropic-ai/sdk";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Plan, PlanStep } from "@eva/shared";
import { callClaude, withRetries } from "./lib/claude";
import type { WorkerEnv } from "./lib/env";
import { EXECUTOR_SYSTEM_PROMPT } from "./prompts/executor";

export type StepOutput = { step: PlanStep; content: string };

function buildStepUserMessage(params: {
  objetivo: string;
  plan: Plan;
  previousOutputs: StepOutput[];
  currentStep: PlanStep;
}): string {
  const { objetivo, plan, previousOutputs, currentStep } = params;

  const planoTexto = plan.steps
    .map(
      (s) =>
        `${s.ordem}. ${s.descricao}${s.tipo_entregavel ? ` [entregável: ${s.tipo_entregavel}]` : ""}`,
    )
    .join("\n");

  const contexto = previousOutputs.length
    ? previousOutputs
        .map((o) => `--- Resultado do step ${o.step.ordem} (${o.step.descricao}) ---\n${o.content}`)
        .join("\n\n")
    : "(nenhum step anterior)";

  return [
    `OBJETIVO DO USUÁRIO:\n${objetivo}`,
    `PLANO COMPLETO:\n${planoTexto}`,
    `RESULTADOS DOS STEPS ANTERIORES:\n${contexto}`,
    `STEP ATUAL A EXECUTAR:\n${currentStep.ordem}. ${currentStep.descricao}${currentStep.tipo_entregavel ? ` [produz entregável: ${currentStep.tipo_entregavel}]` : ""}`,
  ].join("\n\n");
}

/**
 * Executa os steps em sequência (paralelismo fora do escopo do MVP).
 * Cada step: status running → Claude (retry 2× com backoff, timeout 10 min
 * via client) → output persistido → status done. Falha marca o step failed
 * e propaga o erro para o runner.
 */
export async function executeSteps(params: {
  client: Anthropic;
  env: WorkerEnv;
  supabase: SupabaseClient;
  jobId: string;
  objetivo: string;
  plan: Plan;
}): Promise<StepOutput[]> {
  const { client, env, supabase, jobId, objetivo, plan } = params;

  const { data: stepRows, error: stepsError } = await supabase
    .from("job_steps")
    .select("id, ordem")
    .eq("job_id", jobId)
    .order("ordem");
  if (stepsError || !stepRows) {
    throw new Error("Erro ao carregar os steps do job no banco.");
  }
  const stepIdByOrdem = new Map<number, string>(
    stepRows.map((row) => [row.ordem as number, row.id as string]),
  );

  const outputs: StepOutput[] = [];

  for (const step of [...plan.steps].sort((a, b) => a.ordem - b.ordem)) {
    const stepId = stepIdByOrdem.get(step.ordem);
    if (!stepId) throw new Error(`Step ${step.ordem} não encontrado no banco.`);

    await supabase
      .from("job_steps")
      .update({ status: "running", started_at: new Date().toISOString() })
      .eq("id", stepId);

    try {
      const content = await withRetries(() =>
        callClaude(client, env, {
          system: EXECUTOR_SYSTEM_PROMPT,
          messages: [
            {
              role: "user",
              content: buildStepUserMessage({
                objetivo,
                plan,
                previousOutputs: outputs,
                currentStep: step,
              }),
            },
          ],
        }),
      );

      await supabase
        .from("job_steps")
        .update({
          status: "done",
          output: { content },
          finished_at: new Date().toISOString(),
        })
        .eq("id", stepId);

      outputs.push({ step, content });
    } catch (error) {
      await supabase
        .from("job_steps")
        .update({ status: "failed", finished_at: new Date().toISOString() })
        .eq("id", stepId);
      const motivo = error instanceof Error ? error.message : String(error);
      throw new Error(`Falha no step ${step.ordem} (${step.descricao}): ${motivo}`);
    }
  }

  return outputs;
}
