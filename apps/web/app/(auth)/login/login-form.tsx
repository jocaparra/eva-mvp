"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { createClient } from "@/lib/supabase/client";
import { GoogleButton } from "../google-button";

const loginSchema = z.object({
  email: z.email("Digite um e-mail válido."),
  password: z.string().min(1, "Digite sua senha."),
});

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  invalid_credentials: "E-mail ou senha incorretos.",
  email_not_confirmed: "Confirme seu e-mail antes de entrar. Verifique sua caixa de entrada.",
  over_request_rate_limit: "Muitas tentativas. Aguarde alguns minutos e tente de novo.",
};

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const parsed = loginSchema.safeParse({ email, password });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Dados inválidos.");
      return;
    }

    setLoading(true);
    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithPassword(parsed.data);
    setLoading(false);

    if (authError) {
      setError(
        AUTH_ERROR_MESSAGES[authError.code ?? ""] ??
          "Não foi possível entrar. Tente novamente.",
      );
      return;
    }

    router.push("/app");
    router.refresh();
  }

  return (
    <div className="w-full max-w-sm">
      <h1 className="text-2xl font-bold tracking-tight text-eva-text">Entrar</h1>
      <p className="mt-1 mb-8 text-sm text-eva-secondary">
        Acesse sua conta para continuar.
      </p>

      <GoogleButton label="Continuar com Google" onError={setError} />

      <div className="my-6 flex items-center gap-4">
        <div className="h-px flex-1 bg-eva-border" />
        <span className="text-xs text-eva-tertiary">ou</span>
        <div className="h-px flex-1 bg-eva-border" />
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label
            htmlFor="email"
            className="mb-1.5 block text-xs font-semibold text-eva-secondary"
          >
            E-mail
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-eva border border-eva-border px-3.5 py-2.5 text-sm text-eva-text outline-none transition-colors focus:border-eva-text"
            placeholder="voce@empresa.com"
          />
        </div>
        <div>
          <label
            htmlFor="password"
            className="mb-1.5 block text-xs font-semibold text-eva-secondary"
          >
            Senha
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-eva border border-eva-border px-3.5 py-2.5 text-sm text-eva-text outline-none transition-colors focus:border-eva-text"
            placeholder="••••••••"
          />
        </div>

        {error ? (
          <p className="rounded-eva border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={loading}
          className="rounded-eva bg-eva-dark px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1E293B] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Entrando..." : "Entrar"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-eva-secondary">
        Não tem conta?{" "}
        <Link href="/signup" className="font-medium text-eva-text underline">
          Criar conta
        </Link>
      </p>
    </div>
  );
}
