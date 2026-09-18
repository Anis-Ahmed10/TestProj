import ExcelJS from "exceljs";
import { sanitizeText } from "./sanitizeDocumentText";
import type { ProcessingResult } from "./types";

/**
 * XLSX Processor
 *
 * Uses ExcelJS to:
 * 1. Read the workbook from an ArrayBuffer
 * 2. Iterate every sheet → row → cell
 * 3. Sanitize string-type cell values while preserving numbers, dates, formulas, and basic cell styles.
 *    Note: ExcelJS load/write cycles are lossy for complex workbook features such as charts,
 *    pivot tables, data validations, cell comments, and advanced conditional formatting.
 * 4. Write the workbook back to a Blob
 */
export async function processXlsx(file: File): Promise<ProcessingResult> {
  const arrayBuffer = await file.arrayBuffer();

  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(arrayBuffer);

  workbook.eachSheet((worksheet) => {
    worksheet.eachRow({ includeEmpty: false }, (row) => {
      row.eachCell({ includeEmpty: false }, (cell) => {
        if (typeof cell.value === "string") {
          cell.value = sanitizeText(cell.value);
        } else if (cell.value && typeof cell.value === "object") {
          // Handle rich text cell values if present
          if (
            "richText" in cell.value &&
            Array.isArray(
              (cell.value as { richText?: { text?: string }[] }).richText,
            )
          ) {
            (
              cell.value as { richText?: { text?: string }[] }
            ).richText?.forEach((rt) => {
              if (typeof rt.text === "string") {
                rt.text = sanitizeText(rt.text);
              }
            });
          }
        }
      });
    });
  });

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

  const baseName = file.name.replace(/\.xlsx$/i, "");
  return { blob, filename: `${baseName}_sanitized.xlsx` };
}
