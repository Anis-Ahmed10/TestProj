import { sanitizeText } from "./sanitizeDocumentText";
import type { ProcessingResult } from "./types";

/**
 * TXT Processor
 *
 * Reads the file as UTF-8 text, sanitizes the entire string, and
 * returns a new .txt Blob. No structural concerns — plain text.
 */
export async function processTxt(file: File): Promise<ProcessingResult> {
  const text = await file.text();
  const sanitized = sanitizeText(text);
  const blob = new Blob([sanitized], { type: "text/plain;charset=utf-8" });
  const baseName = file.name.replace(/\.txt$/i, "");

  return { blob, filename: `${baseName}_sanitized.txt` };
}
