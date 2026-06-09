import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Callback de OAuth (Google) e de confirmação de e-mail.
 * Troca o código por sessão e redireciona — o middleware decide entre
 * /app (aprovado) e /aguardando (pendente/rejeitado).
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}/app`);
    }
  }

  return NextResponse.redirect(
    `${origin}/login?erro=N%C3%A3o%20foi%20poss%C3%ADvel%20confirmar%20o%20acesso.%20Tente%20de%20novo.`,
  );
}
