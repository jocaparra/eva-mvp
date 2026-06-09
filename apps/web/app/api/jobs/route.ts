import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { enqueueJob } from "@/lib/queue";

const createJobSchema = z.object({
  prompt: z
    .string()
    .trim()
    .min(8, "Descreva o objetivo com mais detalhes (mínimo 8 caracteres).")
    .max(4000, "O objetivo é longo demais (máximo 4000 caracteres)."),
});

const MAX_JOBS_PER_HOUR = 10;

function deriveTitle(prompt: string): string {
  const singleLine = prompt.replace(/\s+/g, " ").trim();
  return singleLine.length > 80 ? `${singleLine.slice(0, 77)}...` : singleLine;
}

/**
 * Cria um job (status queued), a mensagem inicial do usuário e enfileira
 * a execução no pg-boss para o worker consumir.
 */
export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Autenticação necessária." }, { status: 401 });
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("status")
    .eq("id", user.id)
    .single();
  if (profile?.status !== "approved") {
    return NextResponse.json({ error: "Conta ainda não aprovada." }, { status: 403 });
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "Corpo da requisição inválido." }, { status: 400 });
  }

  const parsed = createJobSchema.safeParse(payload);
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? "Dados inválidos." },
      { status: 400 },
    );
  }

  // Rate limit: protege custo de LLM (regra 10 do spec).
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
  const { count } = await supabase
    .from("jobs")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id)
    .gte("created_at", oneHourAgo);
  if ((count ?? 0) >= MAX_JOBS_PER_HOUR) {
    return NextResponse.json(
      {
        error: `Limite de ${MAX_JOBS_PER_HOUR} jobs por hora atingido. Aguarde um pouco antes de criar outro.`,
      },
      { status: 429 },
    );
  }

  const { data: job, error: insertError } = await supabase
    .from("jobs")
    .insert({
      user_id: user.id,
      title: deriveTitle(parsed.data.prompt),
      prompt: parsed.data.prompt,
      status: "queued",
    })
    .select("id")
    .single();

  if (insertError || !job) {
    return NextResponse.json(
      { error: "Não foi possível criar o job. Tente novamente." },
      { status: 500 },
    );
  }

  await supabase.from("messages").insert({
    job_id: job.id,
    role: "user",
    content: parsed.data.prompt,
  });

  try {
    await enqueueJob(job.id);
  } catch (enqueueError) {
    console.error(
      "[api/jobs] falha no enqueue:",
      enqueueError instanceof Error ? enqueueError.message : enqueueError,
    );
    await supabase
      .from("jobs")
      .update({
        status: "failed",
        error: "Não foi possível enfileirar a execução. Tente novamente em instantes.",
      })
      .eq("id", job.id);
    return NextResponse.json(
      { error: "Não foi possível iniciar a execução. Tente novamente." },
      { status: 500 },
    );
  }

  return NextResponse.json({ id: job.id }, { status: 201 });
}
