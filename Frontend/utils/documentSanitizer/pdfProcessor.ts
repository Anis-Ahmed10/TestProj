import * as pdfjsLib from "pdfjs-dist";
import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  ImageRun,
  AlignmentType,
  SectionType,
} from "docx";
import { processDocx } from "./docxProcessor";
import type { ProcessingResult } from "./types";
import { MAX_PDF_PAGES } from "@/constants";

// Configure pdfjs-dist worker via versioned CDN for browser & export build reliability
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

const PT_TO_TWIP = 20; // 1 point = 20 twips

// ------------------------------------------------------------
// Types
// ------------------------------------------------------------

export interface TextSpan {
  text: string;
  fontName: string;
  fontSize: number;
  bold: boolean;
  italic: boolean;
  x: number;
  y: number;
}

export interface TextLine {
  y: number;
  spans: TextSpan[];
}

export interface ExtractedImage {
  id: string;
  width: number;
  height: number;
  data: Uint8Array;
}

export interface PageContent {
  width: number; // in PDF points
  height: number; // in PDF points
  lines: TextLine[];
  images: ExtractedImage[];
}

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------

/**
 * Strip PDF font-subset prefixes such as "ABCDEF+Arial" -> "Arial".
 */
function cleanFontName(rawName: string): string {
  const match = rawName.match(/^[A-Z]{6}\+(.+)$/);
  return match ? match[1] : rawName;
}

/**
 * Heuristic for bold/italic detection based on font name.
 */
function guessStyleFromFontName(fontName: string) {
  const lower = fontName.toLowerCase();
  return {
    bold: /bold|black|heavy/.test(lower),
    italic: /italic|oblique/.test(lower),
  };
}

/**
 * Safely get font name from page.commonObjs
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function safeGetFontName(page: any, internalFontName: string): string {
  try {
    const fontObj = page.commonObjs.get(internalFontName);
    return (fontObj && fontObj.name) || internalFontName || "";
  } catch {
    return internalFontName || "";
  }
}

/**
 * Calculate paragraph alignment based on horizontal position (x) relative to page width.
 */
function alignmentFor(
  x: number,
  pageWidth: number,
): (typeof AlignmentType)[keyof typeof AlignmentType] {
  if (x > pageWidth * 0.65) return AlignmentType.RIGHT;
  if (x > pageWidth * 0.3) return AlignmentType.CENTER;
  return AlignmentType.LEFT;
}

/**
 * Browser-compatible image extraction using Canvas
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function extractImages(
  page: any,
  opList: any,
): Promise<ExtractedImage[]> {
  const images: ExtractedImage[] = [];
  const OPS = pdfjsLib.OPS;

  if (!opList || !opList.fnArray) return images;

  for (let i = 0; i < opList.fnArray.length; i++) {
    const fn = opList.fnArray[i];
    if (fn !== OPS.paintImageXObject && fn !== OPS.paintInlineImageXObject)
      continue;

    const objId = opList.argsArray[i][0];

    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const img: any = await Promise.race([
        new Promise((resolve) => {
          page.objs.get(objId, resolve);
        }),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Image resolution timeout")), 5000),
        ),
      ]);

      if (!img || !img.data || !img.width || !img.height) continue;

      if (typeof document !== "undefined") {
        const canvas = document.createElement("canvas");
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          const imgData = ctx.createImageData(img.width, img.height);
          const src: Uint8ClampedArray = img.data;
          if (src.length === img.width * img.height * 4) {
            imgData.data.set(src);
          } else if (src.length === img.width * img.height * 3) {
            let j = 0;
            for (let k = 0; k < src.length; k += 3) {
              imgData.data[j] = src[k];
              imgData.data[j + 1] = src[k + 1];
              imgData.data[j + 2] = src[k + 2];
              imgData.data[j + 3] = 255;
              j += 4;
            }
          } else {
            let j = 0;
            for (let k = 0; k < src.length; k++) {
              const v = src[k];
              imgData.data[j] = v;
              imgData.data[j + 1] = v;
              imgData.data[j + 2] = v;
              imgData.data[j + 3] = 255;
              j += 4;
            }
          }
          ctx.putImageData(imgData, 0, 0);

          const blob = await new Promise<Blob | null>((r) =>
            canvas.toBlob(r, "image/jpeg", 0.85),
          );

          if (blob) {
            const arrayBuf = await blob.arrayBuffer();
            images.push({
              id: String(objId),
              width: img.width,
              height: img.height,
              data: new Uint8Array(arrayBuf),
            });
          }
        }
      }
    } catch (e) {
      console.warn(
        `Warning: could not extract image ${objId}: ${(e as Error).message}`,
      );
    }
  }

  return images;
}

// ------------------------------------------------------------
// Extract Page Content from PDF
// ------------------------------------------------------------

export async function extractPdfContent(
  pdfData: Uint8Array,
): Promise<PageContent[]> {
  const loadingTask = pdfjsLib.getDocument({
    data: pdfData,
    useSystemFonts: true,
  });
  const pdfDoc = await loadingTask.promise;

  if (pdfDoc.numPages > MAX_PDF_PAGES) {
    throw new Error(
      `PDF contains ${pdfDoc.numPages} pages, exceeding the maximum allowed limit of ${MAX_PDF_PAGES} pages.`,
    );
  }

  const pages: PageContent[] = [];

  for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: 1 });

    // Build the operator list first - populates page.commonObjs with font objects
    const opList = await page.getOperatorList();
    const textContent = await page.getTextContent();

    const linesByY = new Map<number, TextSpan[]>();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const item of textContent.items as any[]) {
      if (!item.str) continue;

      const rawFontName = safeGetFontName(page, item.fontName);
      const fontName = cleanFontName(rawFontName);
      const { bold, italic } = guessStyleFromFontName(fontName);

      const span: TextSpan = {
        text: item.str,
        fontName,
        fontSize:
          Math.round(Math.hypot(item.transform[2], item.transform[3])) || 12,
        bold,
        italic,
        x: item.transform[4],
        y: item.transform[5],
      };

      const yKey = Math.round(span.y / 2) * 2;
      if (!linesByY.has(yKey)) linesByY.set(yKey, []);
      linesByY.get(yKey)!.push(span);
    }

    const lines: TextLine[] = Array.from(linesByY.entries())
      .sort((a, b) => b[0] - a[0]) // PDF Y grows upward -> top to bottom
      .map(([y, spans]) => ({
        y,
        spans: spans.sort((a, b) => a.x - b.x),
      }));

    const images = await extractImages(page, opList);

    pages.push({
      width: viewport.width,
      height: viewport.height,
      lines,
      images,
    });

    // Yield main thread execution after each page loop to keep UI responsive
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  return pages;
}

// ------------------------------------------------------------
// Convert PDF -> DOCX Blob
// ------------------------------------------------------------

export async function convertPdfToDocxBlob(file: File): Promise<Blob> {
  const arrayBuffer = await file.arrayBuffer();
  const pdfData = new Uint8Array(arrayBuffer);
  const pages = await extractPdfContent(pdfData);

  const sections = pages.map((page, index) => {
    const children: Paragraph[] = [];

    for (const line of page.lines) {
      const runs = line.spans.map(
        (span) =>
          new TextRun({
            text: span.text,
            bold: span.bold,
            italics: span.italic,
            size: Math.max(1, Math.round(span.fontSize * 2)), // half-points
            font: span.fontName || undefined,
          }),
      );

      const firstX = line.spans[0]?.x ?? 0;

      children.push(
        new Paragraph({
          children: runs,
          alignment: alignmentFor(firstX, page.width),
          spacing: { before: 0, after: 0 },
        }),
      );
    }

    for (const image of page.images) {
      try {
        const displayWidth = Math.min(image.width, page.width);
        const displayHeight = displayWidth * (image.height / image.width);

        children.push(
          new Paragraph({
            children: [
              new ImageRun({
                data: image.data,
                transformation: { width: displayWidth, height: displayHeight },
              }),
            ],
          }),
        );
      } catch (e) {
        console.warn(
          `Warning: could not embed image ${image.id}: ${(e as Error).message}`,
        );
      }
    }

    return {
      properties: {
        type: index === 0 ? undefined : SectionType.NEXT_PAGE,
        page: {
          size: {
            width: Math.round(page.width * PT_TO_TWIP),
            height: Math.round(page.height * PT_TO_TWIP),
          },
        },
      },
      children,
    };
  });

  const doc = new Document({ sections });
  return await Packer.toBlob(doc);
}

// ------------------------------------------------------------
// Main Entry Point: Convert PDF to DOCX then sanitize using docxProcessor
// ------------------------------------------------------------

export async function processPdf(file: File): Promise<ProcessingResult> {
  const docxBlob = await convertPdfToDocxBlob(file);
  const baseName = file.name.replace(/\.pdf$/i, "");
  const docxFile = new File([docxBlob], `${baseName}.docx`, {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });

  return await processDocx(docxFile);
}
