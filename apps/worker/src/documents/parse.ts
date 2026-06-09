/**
 * Converte o texto estruturado do EVA Executor em um modelo de documento
 * simples: seções com título e linhas (parágrafos/bullets) + tabelas.
 */

export type DocSection = {
  title: string;
  lines: string[];
};

export type DocTable = {
  header: string[];
  rows: string[][];
};

export type ParsedDocument = {
  sections: DocSection[];
  tables: DocTable[];
};

const SECTION_HEADING_REGEX =
  /^(?:#{1,3}\s+|(?:se[çc][ãa]o|slide|parte)\s+\d+\s*[:.\-–]\s*|\d+[.)]\s+)(.+)$/i;

function isTableRow(line: string): boolean {
  return line.includes("|") && line.split("|").filter((c) => c.trim()).length >= 2;
}

function isSeparatorRow(line: string): boolean {
  return /^[\s|:\-–=]+$/.test(line);
}

export function parseExecutorOutput(raw: string): ParsedDocument {
  const lines = raw.split("\n").map((l) => l.trim());

  const sections: DocSection[] = [];
  const tables: DocTable[] = [];
  let current: DocSection | null = null;
  let currentTable: DocTable | null = null;

  function flushTable(): void {
    if (currentTable && currentTable.rows.length > 0) {
      tables.push(currentTable);
    }
    currentTable = null;
  }

  for (const line of lines) {
    if (!line) {
      flushTable();
      continue;
    }

    if (isTableRow(line)) {
      if (isSeparatorRow(line)) continue;
      const cells = line
        .split("|")
        .map((c) => c.trim())
        .filter((c, index, all) => !(c === "" && (index === 0 || index === all.length - 1)));
      if (!currentTable) {
        currentTable = { header: cells, rows: [] };
      } else {
        currentTable.rows.push(cells);
      }
      continue;
    }
    flushTable();

    const headingMatch = line.match(SECTION_HEADING_REGEX);
    if (headingMatch?.[1] && headingMatch[1].length <= 120) {
      current = { title: headingMatch[1].trim(), lines: [] };
      sections.push(current);
      continue;
    }

    const content = line.replace(/^[-•*]\s+/, "").trim();
    if (!current) {
      current = { title: "Conteúdo", lines: [] };
      sections.push(current);
    }
    if (content) current.lines.push(content);
  }
  flushTable();

  if (sections.length === 0) {
    sections.push({ title: "Conteúdo", lines: [raw.trim()] });
  }

  return { sections, tables };
}
