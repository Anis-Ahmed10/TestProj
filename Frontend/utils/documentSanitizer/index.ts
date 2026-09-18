import { processTxt } from "./txtProcessor";
import { processCsv } from "./csvProcessor";
import { processDocx } from "./docxProcessor";
import { processXlsx } from "./xlsxProcessor";
import type { DocumentProcessor, ProcessingResult } from "./types";

export type { ProcessingResult };

/**
 * Lazy-load the PDF processor to avoid bundling pdfjs-dist during
 * server-side rendering / static build. pdfjs-dist references Node's
 * `canvas` package which is unavailable in Next.js browser bundles.
 */
const lazyProcessPdf: DocumentProcessor = async (file) => {
  const { processPdf } = await import("./pdfProcessor");
  return processPdf(file);
};

const SUPPORTED_EXTENSIONS: Record<string, DocumentProcessor> = {
  ".txt": processTxt,
  ".csv": processCsv,
  ".docx": processDocx,
  ".xlsx": processXlsx,
  ".pdf": lazyProcessPdf,
};

export const ACCEPTED_EXTENSIONS = Object.keys(SUPPORTED_EXTENSIONS);

export const ACCEPTED_MIME_TYPES = [
  "text/plain",
  "text/csv",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/pdf",
];

function getFileExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot).toLowerCase() : "";
}

export function isSupported(file: File): boolean {
  return getFileExtension(file.name) in SUPPORTED_EXTENSIONS;
}

export async function processDocument(file: File): Promise<ProcessingResult> {
  const ext = getFileExtension(file.name);
  const processor = SUPPORTED_EXTENSIONS[ext];

  if (!processor) {
    throw new Error(
      `Unsupported file format: "${ext}". Supported: ${ACCEPTED_EXTENSIONS.join(
        ", ",
      )}`,
    );
  }

  return processor(file);
}
