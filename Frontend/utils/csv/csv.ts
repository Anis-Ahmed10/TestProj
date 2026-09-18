/** Byte-order mark, so Excel reads the file as UTF-8 rather than the system codepage. */
export const CSV_BOM = "\uFEFF";

/** Quotes a CSV cell, prefixing `'` so spreadsheets treat a formula-looking value as text. */
export function escapeCsvCell(value: unknown): string {
  const s = String(value ?? "");
  const guarded = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return `"${guarded.replace(/"/g, '""')}"`;
}

export function toCsv(rows: unknown[][]): string {
  return rows.map((row) => row.map(escapeCsvCell).join(",")).join("\r\n");
}
