import Papa from "papaparse";
import { sanitizeText } from "./sanitizeDocumentText";
import type { ProcessingResult } from "./types";

/**
 * CSV Processor
 *
 * Parses the CSV into a 2D array, sanitizes each cell value individually
 * (preserving the table structure), and reconstructs the CSV.
 */
export async function processCsv(file: File): Promise<ProcessingResult> {
  const text = await file.text();

  const parsed = Papa.parse<string[]>(text, {
    header: false,
    skipEmptyLines: false,
  });

  const sanitizedData = parsed.data.map((row) =>
    row.map((cell) => sanitizeText(cell)),
  );

  const delimiter =
    parsed.meta && parsed.meta.delimiter ? parsed.meta.delimiter : ",";

  const reconstructed = Papa.unparse(sanitizedData, {
    delimiter,
    newline: "\r\n",
  });

  const blob = new Blob([reconstructed], {
    type: "text/csv;charset=utf-8",
  });
  const baseName = file.name.replace(/\.csv$/i, "");

  return { blob, filename: `${baseName}_sanitized.csv` };
}
