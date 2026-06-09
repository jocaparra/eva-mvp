import ExcelJS from "exceljs";
import type { ParsedDocument } from "./parse";

/** Gera um XLSX a partir das tabelas (e seções) do documento parseado. */
export async function generateXlsx(
  title: string,
  doc: ParsedDocument,
): Promise<Buffer> {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = "EVA";

  if (doc.tables.length > 0) {
    doc.tables.forEach((table, index) => {
      const sheet = workbook.addWorksheet(`Tabela ${index + 1}`);
      const headerRow = sheet.addRow(table.header);
      headerRow.font = { bold: true };
      headerRow.eachCell((cell) => {
        cell.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: { argb: "FFF8FAFC" },
        };
        cell.border = { bottom: { style: "thin", color: { argb: "FFE2E8F0" } } };
      });
      for (const row of table.rows) {
        sheet.addRow(row);
      }
      sheet.columns.forEach((column) => {
        let max = 12;
        column.eachCell?.({ includeEmpty: false }, (cell) => {
          max = Math.max(max, String(cell.value ?? "").length + 2);
        });
        column.width = Math.min(max, 60);
      });
    });
  } else {
    // Sem tabelas: exporta as seções como planilha de conteúdo.
    const sheet = workbook.addWorksheet("Conteúdo");
    const header = sheet.addRow(["Seção", "Conteúdo"]);
    header.font = { bold: true };
    for (const section of doc.sections) {
      for (const line of section.lines) {
        sheet.addRow([section.title, line]);
      }
    }
    sheet.getColumn(1).width = 32;
    sheet.getColumn(2).width = 100;
  }

  const summary = workbook.addWorksheet("Sobre");
  summary.addRow([title]);
  summary.addRow(["Gerado por EVA — Building Intelligence for the Real Economy."]);

  const buffer = await workbook.xlsx.writeBuffer();
  return Buffer.from(buffer);
}
