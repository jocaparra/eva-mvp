import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Política de Privacidade — EVA",
  description: "Como a EVA trata seus dados pessoais, em conformidade com a LGPD.",
};

export default function PrivacidadePage() {
  return (
    <div className="mx-auto max-w-3xl px-8 py-20">
      <Link href="/" className="text-xs text-eva-tertiary hover:text-eva-text">
        ← Voltar
      </Link>
      <h1 className="mt-4 text-3xl font-bold tracking-tight text-eva-text">
        Política de Privacidade
      </h1>
      <p className="mt-2 text-sm text-eva-tertiary">
        Última atualização: junho de 2026 · Em conformidade com a LGPD (Lei
        13.709/2018)
      </p>

      <div className="mt-10 flex flex-col gap-8 text-sm leading-relaxed text-eva-secondary">
        <section>
          <h2 className="mb-2 text-lg font-semibold text-eva-text">
            1. Dados que coletamos
          </h2>
          <p>
            Coletamos os dados que você fornece no cadastro (nome, e-mail e
            empresa), os dados de autenticação (incluindo login via Google) e o
            conteúdo dos jobs que você cria na plataforma — objetivos, mensagens e
            documentos gerados.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-eva-text">
            2. Como usamos seus dados
          </h2>
          <p>
            Usamos seus dados exclusivamente para operar a plataforma: autenticar
            seu acesso, executar os jobs solicitados (incluindo o processamento do
            conteúdo por modelos de linguagem), gerar os entregáveis e entrar em
            contato sobre sua conta. Não vendemos nem compartilhamos seus dados
            com terceiros para fins de marketing.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-eva-text">
            3. Armazenamento e segurança
          </h2>
          <p>
            Seus dados são armazenados na infraestrutura do Supabase, com controle
            de acesso por linha (RLS): cada usuário acessa apenas os próprios
            dados. Os documentos gerados ficam em bucket privado e só são
            acessíveis por links assinados com expiração de 1 hora.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-eva-text">
            4. Seus direitos (LGPD)
          </h2>
          <p>
            Você pode solicitar a qualquer momento: confirmação do tratamento,
            acesso aos dados, correção, anonimização, portabilidade e exclusão da
            sua conta e de todos os dados associados. Para exercer esses direitos,
            fale com nosso time pelo contato abaixo.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-eva-text">5. Contato</h2>
          <p>
            Encarregado de dados (DPO): entre em contato pelo WhatsApp disponível
            na página inicial ou pelo e-mail indicado no seu contrato. Respondemos
            solicitações de privacidade em até 15 dias.
          </p>
        </section>
      </div>
    </div>
  );
}
