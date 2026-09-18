import ExcelJS from "exceljs";
import type { TestCaseImpactRow } from "@/types/impactAnalyzer";

// ===== Data Mapping =====

export interface RegressionExportRow {
  Test_Case_ID: string;
  Test_Case_Name: string;
  Module: string;
  Recommended_Action: string;
  AI_Confidence: number;
  Reasoning: string;
  Tier: string;
  Test_Type: string;
  Related_Stories: string;
}

export const buildRegressionExportRows = (
  testCases: TestCaseImpactRow[],
): RegressionExportRow[] =>
  testCases.map((tc) => ({
    Test_Case_ID: tc.testCaseKey,
    Test_Case_Name: tc.testCaseName,
    Module: (tc.impactedModules ?? []).join(", "),
    Recommended_Action: tc.recommendedAction,
    AI_Confidence: tc.confidence,
    Reasoning: tc.reason ?? "",
    Tier: tc.tier,
    Test_Type: tc.testType,
    Related_Stories: (tc.relatedStories ?? []).join(", "),
  }));

// ===== Filename Helpers =====

export const sanitizeFilename = (name: string): string =>
  name
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
    .replace(/_{2,}/g, "_")
    .replace(/^_+|_+$/g, "")
    .trim() || "Project";

export const buildRegressionExportFilename = (
  projectName: string,
  date: Date = new Date(),
): string => {
  const sanitized = sanitizeFilename(projectName);
  const dateStr = date.toISOString().slice(0, 10);
  return `Regression_Analysis_${sanitized}_${dateStr}.xlsx`;
};

// ===== Workbook Generation =====

const TABLE_HEADER_FILL: ExcelJS.Fill = {
  type: "pattern",
  pattern: "solid",
  fgColor: { argb: "FF1F3333" },
};

const TABLE_HEADER_FONT: Partial<ExcelJS.Font> = {
  bold: true,
  color: { argb: "FFFFFFFF" },
  size: 11,
};

const THIN_BORDER: Partial<ExcelJS.Borders> = {
  top: { style: "thin", color: { argb: "FFD1D5DB" } },
  bottom: { style: "thin", color: { argb: "FFD1D5DB" } },
  left: { style: "thin", color: { argb: "FFD1D5DB" } },
  right: { style: "thin", color: { argb: "FFD1D5DB" } },
};

function addTestCasesSheet(
  workbook: ExcelJS.Workbook,
  rows: RegressionExportRow[],
): void {
  const sheet = workbook.addWorksheet("Test Cases");

  const columns: {
    header: string;
    key: keyof RegressionExportRow;
    width: number;
  }[] = [
    { header: "Test Case ID", key: "Test_Case_ID", width: 18 },
    { header: "Test Case Name", key: "Test_Case_Name", width: 40 },
    { header: "Module", key: "Module", width: 25 },
    { header: "Recommended Action", key: "Recommended_Action", width: 22 },
    { header: "AI Confidence", key: "AI_Confidence", width: 16 },
    { header: "Reasoning", key: "Reasoning", width: 55 },
    { header: "Tier", key: "Tier", width: 12 },
    { header: "Test Type", key: "Test_Type", width: 14 },
    { header: "Related Stories", key: "Related_Stories", width: 30 },
  ];

  sheet.columns = columns.map((col) => ({
    header: col.header,
    key: col.key,
    width: col.width,
  }));

  // Style header row
  const headerRow = sheet.getRow(1);
  headerRow.eachCell((cell) => {
    cell.fill = TABLE_HEADER_FILL;
    cell.font = TABLE_HEADER_FONT;
    cell.alignment = { vertical: "middle", horizontal: "center" };
    cell.border = THIN_BORDER;
  });
  headerRow.height = 24;

  // Add data rows
  for (const row of rows) {
    const dataRow = sheet.addRow(row);
    dataRow.eachCell({ includeEmpty: true }, (cell) => {
      cell.border = THIN_BORDER;
      cell.alignment = { vertical: "top", wrapText: true };
    });
  }

  // Freeze the header row
  sheet.views = [{ state: "frozen", ySplit: 1 }];
}

export async function generateRegressionAnalysisExcel(
  testCases: TestCaseImpactRow[],
): Promise<Blob> {
  const rows = buildRegressionExportRows(testCases);

  const workbook = new ExcelJS.Workbook();
  workbook.creator = "AI Enhanced ISDM";
  workbook.created = new Date();

  addTestCasesSheet(workbook, rows);

  const buffer = await workbook.xlsx.writeBuffer();
  return new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}
