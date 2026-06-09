import type { ParsedDocument } from "./parse";

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/** Monta o HTML institucional que o Puppeteer imprime em PDF. */
export function buildPdfHtml(title: string, doc: ParsedDocument): string {
  const sectionsHtml = doc.sections
    .map(
      (section) => `
      <section>
        <h2>${escapeHtml(section.title)}</h2>
        ${section.lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("\n")}
      </section>`,
    )
    .join("\n");

  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Helvetica, Arial, sans-serif;
    color: #0F172A;
    font-size: 12px;
    line-height: 1.65;
    padding: 48px 56px;
  }
  h1 { font-size: 26px; letter-spacing: -0.02em; margin-bottom: 6px; }
  .byline { font-size: 11px; color: #64748B; margin-bottom: 32px; }
  h2 {
    font-size: 16px;
    margin: 28px 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid #E2E8F0;
  }
  p { margin-bottom: 8px; color: #1E293B; }
</style>
</head>
<body>
  <h1>${escapeHtml(title)}</h1>
  <p class="byline">Gerado por EVA — Building Intelligence for the Real Economy.</p>
  ${sectionsHtml}
</body>
</html>`;
}

/**
 * Gera o PDF imprimindo o HTML com Puppeteer.
 * Import dinâmico para não carregar o Chromium em testes/boot.
 */
export async function generatePdf(
  title: string,
  doc: ParsedDocument,
): Promise<Buffer> {
  const { default: puppeteer } = await import("puppeteer");
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  try {
    const page = await browser.newPage();
    await page.setContent(buildPdfHtml(title, doc), { waitUntil: "load" });
    const pdf = await page.pdf({
      format: "A4",
      printBackground: true,
      margin: { top: "16mm", bottom: "16mm", left: "0", right: "0" },
    });
    return Buffer.from(pdf);
  } finally {
    await browser.close();
  }
}
