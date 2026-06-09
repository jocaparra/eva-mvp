"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";

const promptSchema = z
  .string()
  .trim()
  .min(8, "Descreva o objetivo com mais detalhes (mínimo 8 caracteres).")
  .max(4000, "O objetivo é longo demais (máximo 4000 caracteres).");

const EXAMPLES = [
  "Crie um teaser da empresa X",
  "Analise o setor de saneamento no Brasil",
  "Compare múltiplos de empresas de SaaS na B3",
];

export function NewJobForm() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const parsed = promptSchema.safeParse(prompt);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Objetivo inválido.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: parsed.data }),
      });
      const body = (await response.json()) as { id?: string; error?: string };
      if (!response.ok || !body.id) {
        setError(body.error ?? "Não foi possível criar o job. Tente novamente.");
        setLoading(false);
        return;
      }
      router.push(`/app/jobs/${body.id}`);
    } catch {
      setError("Falha de conexão. Verifique sua internet e tente de novo.");
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-2xl">
      <h1 className="text-center text-3xl font-bold tracking-tight text-eva-text">
        O que a EVA deve executar?
      </h1>
      <p className="mt-2 text-center text-sm text-eva-secondary">
        Descreva o objetivo. A EVA planeja, executa e entrega o documento pronto.
      </p>

      <form onSubmit={handleSubmit} className="mt-8">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          placeholder="Ex.: Crie um CIM da empresa XPTO com análise de mercado e múltiplos comparáveis"
          className="w-full resize-none rounded-eva border border-eva-border px-4 py-3.5 text-sm text-eva-text outline-none transition-colors focus:border-eva-text"
        />

        {error ? (
          <p className="mt-3 rounded-eva border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        <div className="mt-4 flex items-center justify-between gap-4">
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setPrompt(example)}
                className="rounded-full border border-eva-border bg-white px-3.5 py-1.5 text-xs text-eva-secondary transition-colors hover:bg-eva-bg-alt hover:text-eva-text"
              >
                {example}
              </button>
            ))}
          </div>
          <button
            type="submit"
            disabled={loading}
            className="shrink-0 rounded-eva bg-eva-dark px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1E293B] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Criando..." : "Executar"}
          </button>
        </div>
      </form>
    </div>
  );
}
