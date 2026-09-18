import PizZip from "pizzip";
import { sanitizeText } from "./sanitizeDocumentText";
import type { ProcessingResult } from "./types";

/**
 * DOCX Processor
 *
 * A DOCX file is a ZIP archive containing XML files. This processor:
 * 1. Unzips the DOCX
 * 2. Parses the XML files that contain text content (document.xml, headers, footers, etc.)
 * 3. Walks all <w:t> text nodes and sanitizes their text content
 * 4. Leaves all XML structure, styles, images, tables, etc. completely intact
 * 5. Re-zips and returns the result
 *
 * This approach provides maximum fidelity — all formatting, images, tables,
 * headers, footers, and document metadata are preserved exactly.
 */

/** XML part paths inside a DOCX that may contain user-visible text */
const TEXT_BEARING_PARTS = [
  "word/document.xml",
  "word/header1.xml",
  "word/header2.xml",
  "word/header3.xml",
  "word/footer1.xml",
  "word/footer2.xml",
  "word/footer3.xml",
  "word/comments.xml",
  "word/endnotes.xml",
  "word/footnotes.xml",
];

/**
 * Sanitize all <w:t ...>TEXT</w:t> elements in an XML string using native DOMParser.
 *
 * DOMParser correctly parses XML node trees without fragile regex matches
 * or nested tag mis-scoping (e.g. <w:pPr>).
 */
function sanitizeXmlTextNodes(xmlContent: string): string {
  if (
    typeof DOMParser === "undefined" ||
    typeof XMLSerializer === "undefined"
  ) {
    throw new Error(
      "XML sanitization failed: DOMParser or XMLSerializer is not available.",
    );
  }

  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlContent, "application/xml");

    const parserError = doc.querySelector("parsererror");
    if (parserError) {
      throw new Error(
        `Unparseable OOXML part: ${parserError.textContent ?? "unknown"}`,
      );
    }

    const processedNodes = new Set<Node>();

    // 1. Process paragraph by paragraph to sanitize text split across multiple runs (<w:r><w:t>)
    const paragraphs = doc.querySelectorAll("w\\:p, p");
    paragraphs.forEach((p) => {
      const textNodes = p.querySelectorAll("w\\:t, a\\:t, t");
      if (textNodes.length === 0) return;

      textNodes.forEach((node) => processedNodes.add(node));

      const fullText = Array.from(textNodes)
        .map((node) => node.textContent ?? "")
        .join("");

      if (!fullText.trim()) return;

      const sanitized = sanitizeText(fullText);
      if (sanitized !== fullText) {
        const firstNode = textNodes[0];
        firstNode.textContent = sanitized;
        if (firstNode.nodeType === 1) {
          const elem = firstNode as Element;
          if (!elem.hasAttribute("xml:space")) {
            elem.setAttribute("xml:space", "preserve");
          }
        }
        for (let i = 1; i < textNodes.length; i++) {
          textNodes[i].textContent = "";
        }
      }
    });

    // 2. Fallback: process any standalone text nodes outside <w:p>
    const allTextNodes = doc.querySelectorAll("w\\:t, a\\:t, t");
    allTextNodes.forEach((node) => {
      if (processedNodes.has(node)) return;

      const originalText = node.textContent ?? "";
      if (!originalText) return;

      const sanitized = sanitizeText(originalText);
      if (sanitized !== originalText) {
        node.textContent = sanitized;
        if (node.nodeType === 1) {
          const elem = node as Element;
          if (!elem.hasAttribute("xml:space")) {
            elem.setAttribute("xml:space", "preserve");
          }
        }
      }
    });

    return new XMLSerializer().serializeToString(doc);
  } catch (err) {
    throw err instanceof Error ? err : new Error("XML sanitization failed");
  }
}

export async function processDocx(file: File): Promise<ProcessingResult> {
  const arrayBuffer = await file.arrayBuffer();
  const zip = new PizZip(arrayBuffer);

  const FIXED_DATE = new Date(0);

  // Process each text-bearing XML part
  for (const partPath of TEXT_BEARING_PARTS) {
    const entry = zip.file(partPath);
    if (entry) {
      const xmlContent = entry.asText();
      const sanitizedXml = sanitizeXmlTextNodes(xmlContent);
      zip.file(partPath, sanitizedXml, { date: FIXED_DATE });
    }
  }

  // Also process any additional headers/footers that might exist
  for (const [relativePath, zipEntry] of Object.entries(zip.files)) {
    if (
      /^word\/(header|footer)\d+\.xml$/i.test(relativePath) &&
      !TEXT_BEARING_PARTS.includes(relativePath)
    ) {
      const xmlContent = zipEntry.asText();
      const sanitizedXml = sanitizeXmlTextNodes(xmlContent);
      zip.file(relativePath, sanitizedXml, { date: FIXED_DATE });
    }
  }

  const output = zip.generate({
    type: "blob",
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    compression: "DEFLATE",
  });

  const baseName = file.name.replace(/\.docx$/i, "");

  return { blob: output, filename: `${baseName}_sanitized.docx` };
}
