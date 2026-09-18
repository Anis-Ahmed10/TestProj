export interface ProcessingResult {
  blob: Blob;
  filename: string;
}

export type DocumentProcessor = (file: File) => Promise<ProcessingResult>;
