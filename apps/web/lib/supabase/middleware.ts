import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { getPublicSupabaseEnv } from "@/lib/env";

const PROTECTED_PREFIXES = ["/app", "/admin"];
const AUTH_PAGES = ["/login", "/signup"];

/**
 * Renova a sessão Supabase e aplica o gating da lista de espera (camada 1).
 * A camada 2 é a RLS no banco — nunca confiar só no middleware.
 */
export async function updateSession(request: NextRequest): Promise<NextResponse> {
  let supabaseResponse = NextResponse.next({ request });

  const { url, anonKey } = getPublicSupabaseEnv();
  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        supabaseResponse = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options),
        );
      },
    },
  });

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const path = request.nextUrl.pathname;
  const isProtected = PROTECTED_PREFIXES.some((p) => path.startsWith(p));
  const isAuthPage = AUTH_PAGES.some((p) => path.startsWith(p));
  const isAguardando = path.startsWith("/aguardando");

  function redirect(to: string): NextResponse {
    const redirectUrl = request.nextUrl.clone();
    redirectUrl.pathname = to;
    redirectUrl.search = "";
    const response = NextResponse.redirect(redirectUrl);
    supabaseResponse.cookies.getAll().forEach((cookie) => {
      response.cookies.set(cookie.name, cookie.value);
    });
    return response;
  }

  // Sem login: rotas protegidas e /aguardando exigem autenticação.
  if (!user) {
    if (isProtected || isAguardando) return redirect("/login");
    return supabaseResponse;
  }

  // Com login: buscar status/role do perfil (RLS: usuário lê o próprio).
  const { data: profile } = await supabase
    .from("profiles")
    .select("status, role")
    .eq("id", user.id)
    .single();

  const status = profile?.status ?? "pending";
  const role = profile?.role ?? "user";
  const isApproved = status === "approved";
  const isAdmin = role === "admin";

  if (isProtected) {
    if (!isApproved) return redirect("/aguardando");
    if (path.startsWith("/admin") && !isAdmin) return redirect("/app");
    return supabaseResponse;
  }

  if (isAguardando && isApproved) return redirect("/app");

  if (isAuthPage) {
    return redirect(isApproved ? "/app" : "/aguardando");
  }

  return supabaseResponse;
}
