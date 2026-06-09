"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";

const decisionSchema = z.object({
  profileId: z.uuid("ID de perfil inválido."),
  decision: z.enum(["approved", "rejected"]),
});

export type DecisionResult = { ok: true } | { ok: false; error: string };

/**
 * Aprova ou rejeita um usuário da lista de espera.
 * Roda com a sessão do admin — a RLS (policy profiles_update_admin + trigger
 * protect_profile_columns) garante que só admins conseguem alterar status.
 */
export async function decideProfile(input: {
  profileId: string;
  decision: "approved" | "rejected";
}): Promise<DecisionResult> {
  const parsed = decisionSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Dados inválidos." };
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Sessão expirada. Entre novamente." };

  const { data: me } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();
  if (me?.role !== "admin") {
    return { ok: false, error: "Apenas administradores podem aprovar usuários." };
  }

  const { error } = await supabase
    .from("profiles")
    .update({ status: parsed.data.decision })
    .eq("id", parsed.data.profileId);

  if (error) {
    return { ok: false, error: "Não foi possível atualizar o usuário. Tente de novo." };
  }

  revalidatePath("/admin");
  return { ok: true };
}
