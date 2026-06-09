import type Anthropic from "@anthropic-ai/sdk";
import type { SupabaseClient } from "@supabase/supabase-js";
import { planSchema, type Plan } from "@eva/shared";
import { callClaude } from "./lib/claude";
import type { WorkerEnv } from "./lib/env";
import { PLANNER_FIX_PROMPT, PLANNER_SYSTEM_PROMPT } from "./prompts/planner";

export type ParseResult =
  | { ok: true; plan: Plan }
  | { ok: false; error: string };

/**
 * Faz o parse do JSON retornado pelo Planner, tolerando cercas de markdown
 * e texto acidental ao redor do objeto.
 */
export function parsePlanJson(raw: string): ParseResult {
  let candidate = raw.trim();

  // Remove cercas de código se o modelo desobedecer.
  const fenced = candidate.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenced?.[1]) candidate = fenced[1].trim();

  // Isola o primeiro objeto JSON da resposta.
  const start = candidate.indexOf("{");
  const end = candidate.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    return { ok: false, error: "Nenhum objeto JSON encontrado na resposta." };
  }
  candidate = candidate.slice(start, end + 1);

  let parsed: unknown;
  try {
    parsed = JSON.parse(candidate);
  } catch {
    return { ok: false, error: "JSON malformado (falha no JSON.parse)." };
  }

  const validated = planSchema.safeParse(parsed);
  if (!validated.success) {
    const issues = validated.error.issues
      .map((i) => `${i.path.join(".")}: ${i.message}`)
      .join("; ");
    return { ok: false, error: `Schema inválido: ${issues}` };
  }

  // Garante ordem sequencial 1..N sem buracos.
  const ordens = validated.data.steps.map((s) => s.ordem).sort((a, b) => a - b);
  const sequencial = ordens.every((ordem, index) => ordem === index + 1);
  if (!sequencial) {
    return { ok: false, error: "Steps fora de ordem sequencial (1..N)." };
  }

  return { ok: true, plan: validated.data };
}

/**
 * Planejamento: chama o Claude com o prompt EVA Planner, valida com zod,
 * tenta 1 correção se inválido e persiste em jobs.plan + job_steps.
 */
export async function planJob(params: {
  client: Anthropic;
  env: WorkerEnv;
  supabase: SupabaseClient;
  jobId: string;
  prompt: string;
}): Promise<Plan> {
  const { client, env, supabase, jobId, prompt } = params;

  const firstResponse = await callClaude(client, env, {
    system: PLANNER_SYSTEM_PROMPT,
    messages: [{ role: "user", content: prompt }],
    maxTokens: 2048,
  });

  let result = parsePlanJson(firstResponse);

  if (!result.ok) {
    // 1 tentativa de correção, conforme spec.
    const fixResponse = await callClaude(client, env, {
      system: PLANNER_SYSTEM_PROMPT,
      messages: [
        { role: "user", content: prompt },
        { role: "assistant", content: firstResponse },
        { role: "user", content: PLANNER_FIX_PROMPT.replace("{erro}", result.error) },
      ],
      maxTokens: 2048,
    });
    result = parsePlanJson(fixResponse);
  }

  if (!result.ok) {
    throw new Error(
      `A EVA não conseguiu montar um plano válido para este objetivo (${result.error}). Tente reformular o pedido.`,
    );
  }

  const plan = result.plan;

  const { error: planError } = await supabase
    .from("jobs")
    .update({ plan })
    .eq("id", jobId);
  if (planError) throw new Error(`Erro ao salvar o plano: ${planError.message}`);

  const { error: stepsError } = await supabase.from("job_steps").insert(
    plan.steps.map((step) => ({
      job_id: jobId,
      ordem: step.ordem,
      descricao: step.descricao,
      status: "queued",
    })),
  );
  if (stepsError) throw new Error(`Erro ao salvar os steps: ${stepsError.message}`);

  return plan;
}
