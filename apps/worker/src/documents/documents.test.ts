import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { parseExecutorOutput } from "./parse";
import { generatePptx } from "./pptx";
import { generateDocx } from "./docx";
import { generateXlsx } from "./xlsx";
import { buildPdfHtml } from "./pdf";

const SAMPLE_OUTPUT = `Seção 1: Visão Geral da Empresa
A empresa XPTO atua no setor de saneamento desde 2010.
- Receita estimada de R$ 120 milhões (estimativa)
- EBITDA de R$ 30 milhões

Seção 2: Múltiplos Comparáveis
| Empresa | EV/EBITDA | P/L |
| Sabesp | 6.2x | 9.1x |
| Copasa | 4.8x | 7.4x |

Seção 3: Conclusão
Recomendamos avançar para a due diligence.`;

function isZipBuffer(buffer: Buffer): boolean {
  // PPTX/DOCX/XLSX são ZIPs — assinatura "PK".
  return buffer.length > 4 && buffer[0] === 0x50 && buffer[1] === 0x4b;
}

describe("parseExecutorOutput", () => {
  it("extrai seções com títulos e linhas", () => {
    const doc = parseExecutorOutput(SAMPLE_OUTPUT);
    assert.equal(doc.sections.length, 3);
    assert.equal(doc.sections[0]?.title, "Visão Geral da Empresa");
    assert.ok((doc.sections[0]?.lines.length ?? 0) >= 2);
  });

  it("extrai tabelas com header e linhas", () => {
    const doc = parseExecutorOutput(SAMPLE_OUTPUT);
    assert.equal(doc.tables.length, 1);
    assert.deepEqual(doc.tables[0]?.header, ["Empresa", "EV/EBITDA", "P/L"]);
    assert.equal(doc.tables[0]?.rows.length, 2);
  });

  it("nunca retorna documento vazio", () => {
    const doc = parseExecutorOutput("texto solto sem estrutura");
    assert.ok(doc.sections.length >= 1);
    assert.ok((doc.sections[0]?.lines.length ?? 0) >= 1);
  });
});

describe("geradores de documento", () => {
  const doc = parseExecutorOutput(SAMPLE_OUTPUT);

  it("gera PPTX válido (assinatura ZIP)", async () => {
    const buffer = await generatePptx("Teaser XPTO", doc);
    assert.ok(isZipBuffer(buffer), "PPTX deve ser um ZIP válido");
    assert.ok(buffer.length > 1000);
  });

  it("gera DOCX válido (assinatura ZIP)", async () => {
    const buffer = await generateDocx("Memorando XPTO", doc);
    assert.ok(isZipBuffer(buffer), "DOCX deve ser um ZIP válido");
    assert.ok(buffer.length > 1000);
  });

  it("gera XLSX válido (assinatura ZIP) com tabelas", async () => {
    const buffer = await generateXlsx("Comps XPTO", doc);
    assert.ok(isZipBuffer(buffer), "XLSX deve ser um ZIP válido");
    assert.ok(buffer.length > 1000);
  });

  it("monta HTML de PDF com título e seções escapadas", () => {
    const html = buildPdfHtml('Relatório <XPTO> & "Cia"', doc);
    assert.ok(html.includes("Relatório &lt;XPTO&gt; &amp; &quot;Cia&quot;"));
    assert.ok(html.includes("Visão Geral da Empresa"));
    assert.ok(html.includes("Gerado por EVA"));
  });
});
