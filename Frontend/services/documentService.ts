import { MAX_SIZE_MB } from "@/constants";
import {
  ConfirmUploadResponse,
  DuplicateCheckResponse,
  PreSignedUrlResponse,
  UploadDocumentResult,
} from "@/types/documentUpload";
import { apiRequest } from "@/utils/apiRequest/apiRequest";

const UPLOAD_ENDPOINT = "/api/v1";

const MIME_TYPES: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  doc: "application/msword",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  xls: "application/vnd.ms-excel",
  csv: "text/csv",
  txt: "text/plain",
};

function getContentType(file: File): string {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return MIME_TYPES[ext] ?? "application/octet-stream";
}

async function computeFileHash(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest("SHA-256", arrayBuffer);

  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function checkDuplicate(
  fileHash: string,
  entityId: string,
): Promise<DuplicateCheckResponse> {
  return apiRequest<DuplicateCheckResponse>(
    `${UPLOAD_ENDPOINT}/check-duplicate`,
    {
      method: "POST",
      body: JSON.stringify({ file_hash: fileHash, entity_id: entityId }),
    },
  );
}

async function getPreSignedUrl(
  fileHash: string,
  fileName: string,
  contentType: string,
  folderPath: string,
): Promise<PreSignedUrlResponse> {
  return apiRequest<PreSignedUrlResponse>(`${UPLOAD_ENDPOINT}/presigned-url`, {
    method: "POST",
    body: JSON.stringify({
      file_hash: fileHash,
      file_name: fileName,
      content_type: contentType,
      folder_path: folderPath,
    }),
  });
}

async function uploadToS3(
  file: File,
  preSignedUrl: string,
  contentType: string,
): Promise<void> {
  const response = await fetch(preSignedUrl, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: file,
  });

  if (!response.ok) {
    throw new Error(`S3 upload failed (${response.status})`);
  }
}

async function confirmUpload(
  s3Key: string,
  fileName: string,
  fileHash: string,
  folderPath: string,
  contentType: string,
  entityId: string,
): Promise<ConfirmUploadResponse> {
  return apiRequest<ConfirmUploadResponse>(
    `${UPLOAD_ENDPOINT}/confirm-upload`,
    {
      method: "POST",
      body: JSON.stringify({
        s3_key: s3Key,
        file_name: fileName,
        file_hash: fileHash,
        resource_path: folderPath,
        content_type: contentType,
        entity_id: entityId,
      }),
    },
  );
}

export interface FetchedDocument {
  id: string;
  fileName: string;
  uploadedAt: string;
}

export async function fetchDocuments(
  entityId: string,
): Promise<FetchedDocument[]> {
  const payload = await apiRequest<{
    data?: {
      documents?: {
        document_id: string;
        file_name: string;
        uploaded_at: string;
      }[];
    };
  }>(`${UPLOAD_ENDPOINT}/documents?entity_id=${encodeURIComponent(entityId)}`, {
    method: "GET",
    cache: "no-store",
  });

  const documents = payload?.data?.documents ?? [];
  return documents.map((doc) => ({
    id: doc.document_id,
    fileName: doc.file_name,
    uploadedAt: doc.uploaded_at,
  }));
}

export async function uploadDocument(
  file: File,
  folderPath: string,
  entityId: string,
): Promise<UploadDocumentResult> {
  const normalizedFolderPath = folderPath.replace(/\s+/g, "_");

  // Compute file hash on the original file for deterministic duplicate detection
  const originalFileHash = await computeFileHash(file);

  const duplicateCheck = await checkDuplicate(originalFileHash, entityId);
  if (duplicateCheck.data.is_duplicate) {
    return {
      id: duplicateCheck.data.id,
      documentId: duplicateCheck.data.id,
      title: file.name.replace(/\.[^/.]+$/, ""),
      fileName: duplicateCheck.data.file_name ?? file.name,
      isDuplicate: true,
    };
  }

  // ── Document Sanitization ──────────────────────────────────────
  let sanitizationResult;
  try {
    const { processDocument } = await import("@/utils/documentSanitizer");
    sanitizationResult = await processDocument(file);
  } catch (error) {
    console.error("[AUDIT][SANITIZATION_FAILURE] File sanitization failed.", {
      fileName: file.name,
      fileSize: file.size,
      fileType: file.type,
      error: error instanceof Error ? error.message : String(error),
      timestamp: new Date().toISOString(),
    });
    throw new Error(
      "The document is malformed, corrupted, or could not be sanitized. Please check the file and try again.",
    );
  }

  const sanitizedFile = new File(
    [sanitizationResult.blob],
    sanitizationResult.filename,
    { type: sanitizationResult.blob.type || getContentType(file) },
  );
  if (sanitizedFile.size > MAX_SIZE_MB * 1024 * 1024) {
    throw new Error(
      `Sanitized file size (${(sanitizedFile.size / (1024 * 1024)).toFixed(
        1,
      )} MB) exceeds the maximum allowed limit of ${MAX_SIZE_MB} MB.`,
    );
  }
  const contentType = getContentType(sanitizedFile);
  const preSignedData = await getPreSignedUrl(
    originalFileHash,
    sanitizedFile.name,
    contentType,
    normalizedFolderPath,
  );

  await uploadToS3(
    sanitizedFile,
    preSignedData.data.presigned_url,
    contentType,
  );

  const confirmResult = await confirmUpload(
    preSignedData.data.s3_key,
    sanitizedFile.name,
    originalFileHash,
    normalizedFolderPath,
    contentType,
    entityId,
  );

  return {
    documentId: confirmResult.data.document_id,
    s3Key: preSignedData.data.s3_key,
    title: sanitizedFile.name.replace(/\.[^/.]+$/, ""),
    fileName: sanitizedFile.name,
    isDuplicate: false,
  };
}

export async function deleteDocument(
  documentId: string,
  entityId: string,
): Promise<void> {
  await apiRequest<void>(
    `/api/v1/documents?document_id=${encodeURIComponent(
      documentId,
    )}&entity_id=${encodeURIComponent(entityId)}`,
    {
      method: "DELETE",
    },
  );
}
