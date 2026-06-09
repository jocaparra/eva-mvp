import {
  Document,
  HeadingLevel,
  Packer,
  Paragraph,
  TextRun,
} from "docx";
import type { ParsedDocument } from "./parse";

/** Gera um DOCX institucional a partir do documento parseado. */
export async function generateDocx(
  title: string,
  doc: ParsedDocument,
): Promise<Buffer> {
  const children: Paragraph[] = [
    new Paragraph({
      heading: HeadingLevel.TITLE,
      children: [new TextRun({ text: title, bold: true })],
    }),
    new Paragraph({
      children: [
        new TextRun({
          text: "Gerado por EVA — Building Intelligence for the Real Economy.",
          color: "64748B",
          size: 20,
        }),
      ],
      spacing: { after: 400 },
    }),
  ];

  for (const section of doc.sections) {
    children.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: section.title })],
        spacing: { before: 300, after: 150 },
      }),
    );
    for (const line of section.lines) {
      children.push(
        new Paragraph({
          children: [new TextRun({ text: line, size: 22 })],
          spacing: { after: 120 },
        }),
      );
    }
  }

  const document = new Document({
    sections: [{ children }],
  });

  return Packer.toBuffer(document);
}
