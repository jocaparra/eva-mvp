import PptxGenJSModule from "pptxgenjs";
import type { ParsedDocument } from "./parse";

// Interop CJS/ESM: dependendo do loader, o construtor vem direto ou em .default.
type PptxCtor = typeof PptxGenJSModule;
const PptxGenJS: PptxCtor =
  (PptxGenJSModule as unknown as { default?: PptxCtor }).default ?? PptxGenJSModule;

const COLORS = {
  text: "0F172A",
  secondary: "64748B",
  border: "E2E8F0",
  bgAlt: "F8FAFC",
};

/** Gera um PPTX institucional a partir do documento parseado. */
export async function generatePptx(
  title: string,
  doc: ParsedDocument,
): Promise<Buffer> {
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: "WIDE", width: 13.33, height: 7.5 });
  pptx.layout = "WIDE";

  // Slide de capa
  const cover = pptx.addSlide();
  cover.background = { color: COLORS.bgAlt };
  cover.addText(title, {
    x: 0.8,
    y: 2.6,
    w: 11.7,
    h: 1.6,
    fontSize: 36,
    bold: true,
    color: COLORS.text,
    fontFace: "Arial",
  });
  cover.addText("Gerado por EVA — Building Intelligence for the Real Economy.", {
    x: 0.8,
    y: 4.4,
    w: 11.7,
    h: 0.5,
    fontSize: 14,
    color: COLORS.secondary,
    fontFace: "Arial",
  });

  // Um slide por seção
  for (const section of doc.sections) {
    const slide = pptx.addSlide();
    slide.addText(section.title, {
      x: 0.8,
      y: 0.5,
      w: 11.7,
      h: 0.8,
      fontSize: 24,
      bold: true,
      color: COLORS.text,
      fontFace: "Arial",
    });
    slide.addShape("line", {
      x: 0.8,
      y: 1.4,
      w: 11.7,
      h: 0,
      line: { color: COLORS.border, width: 1 },
    });

    const bullets = section.lines.slice(0, 10);
    if (bullets.length > 0) {
      slide.addText(
        bullets.map((line) => ({
          text: line,
          options: { bullet: { characterCode: "2022", indent: 12 } },
        })),
        {
          x: 0.8,
          y: 1.7,
          w: 11.7,
          h: 5.2,
          fontSize: 14,
          color: COLORS.text,
          fontFace: "Arial",
          valign: "top",
          paraSpaceAfter: 8,
        },
      );
    }
  }

  const output = await pptx.write({ outputType: "nodebuffer" });
  return output as Buffer;
}
