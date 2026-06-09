"use client";

import { useState } from "react";
import Link from "next/link";
import { z } from "zod";
import { createClient } from "@/lib/supabase/client";
import { GoogleButton } from "../google-button";

const signupSchema = z.object({
  fullName: z.string().min(2, "Digite seu nome completo."),
  company: z.string().min(1, "Digite o nome da sua empresa."),
  email: z.email("Digite um e-mail válido."),
  password: z.string().min(8, "A senha precisa ter no mínimo 8 caracteres."),
});

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  user_already_exists: "Já existe uma conta com este e-mail. Tente entrar.",
  weak_password: "Senha fraca demais. Use no mínimo 8 caracteres.",
  over_request_rate_limit: "Muitas tentativas. Aguarde alguns minutos e tente de novo.",
};

export function SignupForm() {
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const parsed = signupSchema.safeParse({ fullName, company, email, password });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Dados inválidos.");
      return;
    }

    setLoading(true);
    const supabase = createClient();
    const { error: authError } = await supabase.auth.signUp({
      email: parsed.data.email,
      password: parsed.data.password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
        data: {
          full_name: parsed.data.fullName,
          company: parsed.data.company,
        },
      },
    });
    setLoading(false);

    if (authError) {
      setError(
        AUTH_ERROR_MESSAGES[authError.code ?? ""] ??
          "Não foi possível criar a conta. Tente novamente.",
      );
      return;
    }

    setDone(true);
  }

  if (done) {
    return (
      <div className="w-full max-w-sm text-center">
        <h1 className="text-2xl font-bold tracking-tight text-eva-text">
          Confirme seu e-mail
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-eva-secondary">
          Enviamos um link de confirmação para <strong>{email}</strong>. Clique no
          link para ativar sua conta. Depois disso, ela passa por análise do nosso
          time.
        </p>
        <Link
          href="/login"
          className="mt-8 inline-block rounded-eva bg-eva-dark px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1E293B]"
        >
          Ir para o login
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full max-w-sm">
      <h1 className="text-2xl font-bold tracking-tight text-eva-text">Criar conta</h1>
      <p className="mt-1 mb-8 text-sm text-eva-secondary">
        Novas contas passam por análise antes da liberação do acesso.
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
            htmlFor="fullName"
            className="mb-1.5 block text-xs font-semibold text-eva-secondary"
          >
            Nome completo
          </label>
          <input
            id="fullName"
            type="text"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded-eva border border-eva-border px-3.5 py-2.5 text-sm text-eva-text outline-none transition-colors focus:border-eva-text"
            placeholder="Seu nome"
          />
        </div>
        <div>
          <label
            htmlFor="company"
            className="mb-1.5 block text-xs font-semibold text-eva-secondary"
          >
            Empresa
          </label>
          <input
            id="company"
            type="text"
            autoComplete="organization"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            className="w-full rounded-eva border border-eva-border px-3.5 py-2.5 text-sm text-eva-text outline-none transition-colors focus:border-eva-text"
            placeholder="Nome da empresa"
          />
        </div>
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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-eva border border-eva-border px-3.5 py-2.5 text-sm text-eva-text outline-none transition-colors focus:border-eva-text"
            placeholder="Mínimo 8 caracteres"
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
          {loading ? "Criando conta..." : "Criar conta"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-eva-secondary">
        Já tem conta?{" "}
        <Link href="/login" className="font-medium text-eva-text underline">
          Entrar
        </Link>
      </p>
    </div>
  );
}
