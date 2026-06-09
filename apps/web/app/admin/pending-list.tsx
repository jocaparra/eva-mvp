"use client";

import { useState, useTransition } from "react";
import { decideProfile } from "./actions";

export type PendingProfile = {
  id: string;
  email: string;
  full_name: string | null;
  company: string | null;
  status: "pending" | "approved" | "rejected";
  created_at: string;
};

const STATUS_LABEL: Record<PendingProfile["status"], string> = {
  pending: "Pendente",
  approved: "Aprovado",
  rejected: "Rejeitado",
};

const STATUS_CLASSES: Record<PendingProfile["status"], string> = {
  pending: "bg-eva-bg-alt text-eva-secondary border border-eva-border",
  approved: "bg-green-50 text-green-700 border border-green-200",
  rejected: "bg-red-50 text-red-700 border border-red-200",
};

export function PendingList({
  profiles,
  mode,
}: {
  profiles: PendingProfile[];
  mode: "pending" | "decided";
}) {
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleDecision(profileId: string, decision: "approved" | "rejected") {
    setError(null);
    startTransition(async () => {
      const result = await decideProfile({ profileId, decision });
      if (!result.ok) setError(result.error);
    });
  }

  if (!profiles.length) {
    return (
      <p className="rounded-eva border border-eva-border bg-eva-bg-alt px-4 py-6 text-center text-sm text-eva-tertiary">
        {mode === "pending" ? "Nenhuma conta pendente." : "Nenhuma decisão ainda."}
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-eva border border-eva-border">
      {error ? (
        <p className="border-b border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </p>
      ) : null}
      <table className="w-full text-left text-sm">
        <thead className="border-b border-eva-border bg-eva-bg-alt text-xs text-eva-secondary">
          <tr>
            <th className="px-4 py-3 font-semibold">Usuário</th>
            <th className="px-4 py-3 font-semibold">Empresa</th>
            <th className="px-4 py-3 font-semibold">Criado em</th>
            <th className="px-4 py-3 font-semibold">
              {mode === "pending" ? "Ações" : "Status"}
            </th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((profile) => (
            <tr key={profile.id} className="border-b border-eva-border last:border-b-0">
              <td className="px-4 py-3">
                <div className="font-medium text-eva-text">
                  {profile.full_name ?? "—"}
                </div>
                <div className="text-xs text-eva-secondary">{profile.email}</div>
              </td>
              <td className="px-4 py-3 text-eva-secondary">
                {profile.company ?? "—"}
              </td>
              <td className="px-4 py-3 text-eva-secondary">
                {new Date(profile.created_at).toLocaleDateString("pt-BR")}
              </td>
              <td className="px-4 py-3">
                {mode === "pending" ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handleDecision(profile.id, "approved")}
                      className="rounded-eva bg-eva-dark px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-[#1E293B] disabled:opacity-50"
                    >
                      Aprovar
                    </button>
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => handleDecision(profile.id, "rejected")}
                      className="rounded-eva border border-eva-border bg-white px-3 py-1.5 text-xs font-semibold text-eva-secondary transition-colors hover:bg-eva-bg-alt disabled:opacity-50"
                    >
                      Rejeitar
                    </button>
                  </div>
                ) : (
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASSES[profile.status]}`}
                  >
                    {STATUS_LABEL[profile.status]}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
