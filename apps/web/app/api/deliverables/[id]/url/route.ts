import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";

const SIGNED_URL_EXPIRY_SECONDS = 3600; // 1 hora, conforme spec

const paramsSchema = z.object({ id: z.uuid("ID de entregável inválido.") });

/**
 * Gera URL assinada (1h) para download de um entregável.
 * A posse é verificada com o client do usuário (RLS); a assinatura usa
 * service role apenas server-side.
 */
export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const rawParams = await context.params;
  const parsed = paramsSchema.safeParse(rawParams);
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? "Parâmetros inválidos." },
      { status: 400 },
    );
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Autenticação necessária." }, { status: 401 });
  }

  // RLS: só retorna se o usuário for dono do job (ou admin).
  const { data: deliverable } = await supabase
    .from("deliverables")
    .select("id, storage_path, filename")
    .eq("id", parsed.data.id)
    .maybeSingle();

  if (!deliverable) {
    return NextResponse.json({ error: "Entregável não encontrado." }, { status: 404 });
  }

  const admin = createAdminClient();
  const { data: signed, error: signError } = await admin.storage
    .from("deliverables")
    .createSignedUrl(deliverable.storage_path, SIGNED_URL_EXPIRY_SECONDS, {
      download: deliverable.filename,
    });

  if (signError || !signed) {
    return NextResponse.json(
      { error: "Não foi possível gerar o link de download. Tente novamente." },
      { status: 500 },
    );
  }

  return NextResponse.json({ url: signed.signedUrl });
}
