import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SignOutButton } from "./signout-button";

export const metadata: Metadata = {
  title: "Conta em análise — EVA",
};

const WHATSAPP_CONTACT_URL =
  "https://api.whatsapp.com/send?phone=5519999560806&text=Ol%C3%A1%2C%20criei%20minha%20conta%20na%20EVA%20e%20aguardo%20a%20libera%C3%A7%C3%A3o%20do%20acesso.";

export default async function AguardandoPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("status")
    .eq("id", user.id)
    .single();

  if (profile?.status === "approved") redirect("/app");

  const rejected = profile?.status === "rejected";

  return (
    <div className="w-full max-w-md text-center">
      <p className="mb-5 text-[11px] font-medium uppercase tracking-[0.14em] text-eva-tertiary">
        {rejected ? "Acesso não liberado" : "Conta em análise"}
      </p>
      <h1 className="text-3xl font-bold tracking-tight text-eva-text">
        {rejected
          ? "Sua conta não foi aprovada."
          : "Sua conta está em análise."}
      </h1>
      <p className="mt-4 text-sm leading-relaxed text-eva-secondary">
        {rejected
          ? "Se acredita que houve um engano, fale com nosso time pelo WhatsApp."
          : "Nosso time libera o acesso em até 24 horas. Você receberá a confirmação por e-mail."}
      </p>
      <div className="mt-8 flex flex-col items-center gap-3">
        <a
          href={WHATSAPP_CONTACT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-eva bg-eva-dark px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1E293B]"
        >
          Falar com o time no WhatsApp
        </a>
        <SignOutButton />
      </div>
    </div>
  );
}
