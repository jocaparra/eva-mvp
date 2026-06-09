import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import "./landing.css";

export const metadata: Metadata = {
  title: "EVA, Building Intelligence for the Real Economy",
  description:
    "EVA executa processos completos de análise, documentação e decisão, sem supervisão constante. The Operating System for Modern Businesses.",
};

const WHATSAPP_DEMO_URL =
  "https://api.whatsapp.com/send?phone=5519999560806&text=Ol%C3%A1%2C%20tenho%20interesse%20ao%20acesso%20antecipado%20da%20EVA.";

export default function LandingPage() {
  return (
    <div className="landing">
      {/* ── 1. NAV ── */}
      <nav className="nav">
        <div className="nav-inner">
          <a href="#" className="nav-brand">
            <Image
              src="/assets/logo-eva-black.png"
              alt="EVA"
              className="logo-mark"
              width={528}
              height={468}
              priority
            />
          </a>
          <div className="nav-right">
            <div className="nav-links">
              <a href="#features">Produto</a>
              <a href="#how">Como funciona</a>
              <a href="#whom">Para quem</a>
            </div>
            <div className="nav-actions">
              <Link href="/login" className="btn-secondary">
                Entrar
              </Link>
              <a
                href={WHATSAPP_DEMO_URL}
                className="btn-primary"
                target="_blank"
                rel="noopener noreferrer"
              >
                Agendar Demo
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* ── 2. HERO ── */}
      <section className="hero">
        <span className="hero-pill">The Operating System for Modern Businesses</span>
        <h1>
          Building Intelligence
          <br />
          for the Real Economy.
        </h1>
        <p className="hero-sub">
          EVA executa processos completos de análise, documentação e decisão, sem
          supervisão constante. Do primeiro dado ao entregável institucional.
        </p>
        <div className="hero-cta">
          <a
            href={WHATSAPP_DEMO_URL}
            className="btn-primary"
            target="_blank"
            rel="noopener noreferrer"
          >
            Agendar Demo
          </a>
          <a href="#how" className="btn-ghost">
            Ver como funciona →
          </a>
        </div>
        <Image
          src="/assets/hero-product.png"
          alt="Interface da EVA gerando um valuation da Apple"
          className="hero-visual"
          width={1024}
          height={682}
          sizes="(max-width: 960px) 100vw, 960px"
          priority
        />
      </section>

      {/* ── 3. METRICS BAR ── */}
      <section className="metrics">
        <div className="container">
          <div className="metrics-grid">
            <div className="metric-item">
              <div className="metric-value">4 min</div>
              <div className="metric-label">Para gerar um CIM completo</div>
            </div>
            <div className="metric-item">
              <div className="metric-value">2×</div>
              <div className="metric-label">Capacidade com o mesmo headcount</div>
            </div>
            <div className="metric-item">
              <div className="metric-value">80%</div>
              <div className="metric-label">Menos due diligence manual</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── 4. PROBLEM ── */}
      <section className="section problem">
        <div className="container">
          <div className="problem-header">
            <p className="eyebrow">O problema</p>
            <h2 className="section-title">Seu time está operando abaixo do potencial.</h2>
          </div>
          <div className="problem-grid">
            <div className="problem-card">
              <div className="card-number">01</div>
              <h3 className="card-title">
                Trabalho operacional consome tempo estratégico
              </h3>
              <p className="card-desc">
                Analistas e sêniors gastam mais de 30% do tempo em apresentações,
                trackers e pesquisas manuais. Tempo que deveria estar em análise e
                relacionamento.
              </p>
            </div>
            <div className="problem-card">
              <div className="card-number">02</div>
              <h3 className="card-title">
                Escalar exige contratar, e contratar é lento e caro
              </h3>
              <p className="card-desc">
                Para aumentar volume, a única opção é aumentar headcount. O custo
                cresce junto com a operação, e a qualidade varia conforme quem executa.
              </p>
            </div>
            <div className="problem-card">
              <div className="card-number">03</div>
              <h3 className="card-title">IA genérica não entende o seu contexto</h3>
              <p className="card-desc">
                ChatGPT e ferramentas genéricas geram rascunhos que precisam ser
                completamente refeitos. Não conhecem seu setor, seus dados, suas
                fontes.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 5. FEATURES ── */}
      <section className="section features" id="features">
        <div className="container">
          <div className="features-header">
            <p className="eyebrow">O que a EVA entrega</p>
            <h2 className="section-title">
              Inteligência que executa, não apenas responde.
            </h2>
          </div>
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">
                <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M4 2h9l5 5v11H4V2z"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M13 2v5h5"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M7 11h6M7 14h4"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <h3 className="card-title">Geração de Materiais Institucionais</h3>
              <p className="card-desc">
                CIM, Pitch Deck, Teaser, Memorando de Investimento, gerados em minutos
                com qualidade pronta para cliente. Não um rascunho. O documento final.
              </p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">
                <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="9" cy="9" r="5.5" stroke="#0F172A" strokeWidth="1.5" />
                  <path
                    d="M13.5 13.5L18 18"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                  <path
                    d="M7 9h4M9 7v4"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <h3 className="card-title">Due Diligence Automatizada</h3>
              <p className="card-desc">
                Análise de data rooms, identificação automática de riscos, Q&amp;A com
                citação de fontes e reconciliação de dados financeiros. Semanas de
                análise em poucas horas.
              </p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">
                <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M3 15l4-6 3 3 5-8 2 3"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M3 17h14"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
              <h3 className="card-title">Análise de Empresas e Setores</h3>
              <p className="card-desc">
                Benchmarks, comps, tendências setoriais, múltiplos de mercado e
                inteligência competitiva. Integrado com B3, Nasdaq, NYSE e GOV.BR.
              </p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">
                <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="10" cy="10" r="7" stroke="#0F172A" strokeWidth="1.5" />
                  <path
                    d="M10 6v4l3 2"
                    stroke="#0F172A"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h3 className="card-title">Execução Assíncrona 24/7</h3>
              <p className="card-desc">
                Jobs rodam mesmo sem o usuário online. Múltiplos agentes em paralelo.
                Pipelines persistentes que entregam quando prontos.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 6. HOW IT WORKS ── */}
      <section className="section how" id="how">
        <div className="container">
          <div className="how-header">
            <p className="eyebrow">Como funciona</p>
            <h2 className="section-title">
              Do comando ao entregável, sem intermediários.
            </h2>
          </div>
          <div className="how-grid">
            <div>
              <p className="how-step-label">01, Input</p>
              <h3 className="how-step-title">Você define o objetivo</h3>
              <p className="how-step-desc">
                Via WhatsApp ou plataforma web. EVA entende contexto, não só comandos.
              </p>
            </div>
            <div>
              <p className="how-step-label">02, Execução</p>
              <h3 className="how-step-title">EVA planeja e executa</h3>
              <p className="how-step-desc">
                Divide o trabalho em subtarefas, aciona agentes especializados em
                paralelo e executa de forma assíncrona.
              </p>
            </div>
            <div>
              <p className="how-step-label">03, Entrega</p>
              <h3 className="how-step-title">Você recebe o entregável pronto</h3>
              <p className="how-step-desc">
                PPT, PDF, DOCX ou Excel, formatado e pronto para ir para o cliente.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 7. FOR WHOM ── */}
      <section className="section whom" id="whom">
        <div className="container">
          <div className="whom-header">
            <p className="eyebrow">Para quem é</p>
            <h2 className="section-title">
              Construída para quem não tem tempo a perder.
            </h2>
          </div>
          <div className="whom-grid">
            <div className="whom-card">
              <p className="whom-role">Investment Banking · PE · VC · M&amp;A</p>
              <h3 className="whom-title">Times de Deals</h3>
              <p className="whom-subtitle">
                Onde a EVA nasceu. Exigência máxima de qualidade institucional,
                velocidade e confidencialidade.
              </p>
              <ul className="whom-list">
                <li>→ CIM e Pitch Deck em minutos</li>
                <li>→ Due diligence em horas</li>
                <li>→ Análise de comps automatizada</li>
                <li>→ Instância dedicada</li>
              </ul>
              <p className="whom-message">
                Dobrar sua capacidade de deals sem contratar mais uma pessoa.
              </p>
            </div>
            <div className="whom-card">
              <p className="whom-role">
                Jurídico · Consultoria · Real Estate · Corporativo
              </p>
              <h3 className="whom-title">Empresas da Economia Real</h3>
              <p className="whom-subtitle">
                Qualquer empresa com alto volume de análise, documentação e processos
                críticos.
              </p>
              <ul className="whom-list">
                <li>→ Relatórios e análises em minutos</li>
                <li>→ Documentos board-ready</li>
                <li>→ Pesquisa avançada em bases internas</li>
                <li>→ Automação de processos repetitivos</li>
              </ul>
              <p className="whom-message">
                Inteligência aplicada ao seu processo, sem a curva de aprendizado de IA
                genérica.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── 8. PROOF ── */}
      <section className="section proof">
        <div className="container">
          <p className="eyebrow">Resultado real</p>
          <blockquote className="proof-quote">
            &quot;A EVA desbloqueou completamente nosso time ao dobrar nossa
            capacidade.{" "}
            <em>
              Estamos no caminho de dobrar nossa quantidade de deals no próximo ano com
              o mesmo headcount.
            </em>
            &quot;
          </blockquote>
          <p className="proof-attribution">
            Principal, Banco de Investimento Middle Market
          </p>
        </div>
      </section>

      {/* ── 9. CTA FINAL ── */}
      <section className="cta-final" id="cta">
        <h2>Pronto para operar em outro nível?</h2>
        <p className="cta-final-sub">
          Agende uma demonstração e veja a EVA executando um caso real do seu setor.
        </p>
        <a
          href={WHATSAPP_DEMO_URL}
          className="btn-inverted"
          target="_blank"
          rel="noopener noreferrer"
        >
          Agendar Demo
        </a>
        <p className="cta-trust">
          Sem compromisso · Resposta em até 24 horas · SOC 2 Type II · LGPD
        </p>
      </section>

      {/* ── 10. FOOTER ── */}
      <footer className="footer">
        <div className="container">
          <div className="footer-inner">
            <div className="footer-left">
              <span className="footer-wordmark">EVA</span>
              <span>© 2026 EVA. Todos os direitos reservados.</span>
            </div>
            <div className="footer-links">
              <a href="#features">Produto</a>
              <a href="#whom">Para quem</a>
              <a href={WHATSAPP_DEMO_URL} target="_blank" rel="noopener noreferrer">
                Contato
              </a>
              <a href="#">Política de Privacidade</a>
            </div>
          </div>
        </div>
      </footer>

      {/* ── EVA STAMP ── */}
      <section className="eva-stamp" aria-hidden="true">
        <div className="eva-stamp-inner">
          <h2 className="eva-stamp-text">EVA</h2>
          <p className="eva-stamp-tag">Building Intelligence for the Real Economy.</p>
        </div>
      </section>
    </div>
  );
}
