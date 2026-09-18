// Parses RFC-compliant CSV text into an array of header-keyed row objects.
export function parseCSV(text: string): Record<string, string>[] {
  const headers: string[] = [];
  const rows: Record<string, string>[] = [];
  let field = "";
  let inQuotes = false;
  let isFirstRow = true;
  let currentRow: string[] = [];

  const commitField = () => {
    currentRow.push(field);
    field = "";
  };
  const commitRow = () => {
    if (!isFirstRow && currentRow.some((v) => v)) {
      rows.push(
        Object.fromEntries(
          headers.map((h, i) => [h.trim(), (currentRow[i] ?? "").trim()]),
        ),
      );
    }
    if (isFirstRow) {
      headers.push(...currentRow.map((h) => h.trim()));
      isFirstRow = false;
    }
    currentRow = [];
  };

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (inQuotes) {
      if (ch === '"' && next === '"') {
        field += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        field += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        commitField();
      } else if (ch === "\r" && next === "\n") {
        commitField();
        commitRow();
        i++;
      } else if (ch === "\n") {
        commitField();
        commitRow();
      } else {
        field += ch;
      }
    }
  }
  if (field || currentRow.length > 0) {
    commitField();
    commitRow();
  }
  return rows;
}
