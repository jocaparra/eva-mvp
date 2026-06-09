import type { DeliverableTipo } from "@eva/shared";
import { parseExecutorOutput } from "./parse";
import { generatePptx } from "./pptx";
import { generateDocx } from "./docx";
import { generateXlsx } from "./xlsx";
import { generatePdf } from "./pdf";

export type GeneratedDocument = {
  buffer: Buffer;
  filename: string;
  contentType: string;
};

const CONTENT_TYPES: Record<DeliverableTipo, string> = {
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  pdf: "application/pdf",
};

function slugify(text: string): string {
  return (
    text
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase()
      .slice(0, 60) || "documento"
  );
}

/** Gera o documento final no formato pedido a partir do output do Executor. */
export async function generateDeliverable(params: {
  tipo: DeliverableTipo;
  title: string;
  content: string;
}): Promise<GeneratedDocument> {
  const { tipo, title, content } = params;
  const doc = parseExecutorOutput(content);

  let buffer: Buffer;
  switch (tipo) {
    case "pptx":
      buffer = await generatePptx(title, doc);
      break;
    case "docx":
      buffer = await generateDocx(title, doc);
      break;
    case "xlsx":
      buffer = await generateXlsx(title, doc);
      break;
    case "pdf":
      buffer = await generatePdf(title, doc);
      break;
  }

  return {
    buffer,
    filename: `${slugify(title)}.${tipo}`,
    contentType: CONTENT_TYPES[tipo],
  };
}
