interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export interface DuplicateCheckData {
  is_duplicate: boolean;
  file_name: string | null;
  id: string;
  message: string;
}

export interface PresignedUrlData {
  presigned_url: string;
  s3_key: string;
  expires_in: number;
}

export interface ConfirmUploadData {
  document_id: string;
  message: string;
}

export type DuplicateCheckResponse = ApiResponse<DuplicateCheckData>;
export type PreSignedUrlResponse = ApiResponse<PresignedUrlData>;
export type ConfirmUploadResponse = ApiResponse<ConfirmUploadData>;

export interface UploadDocumentResult {
  documentId?: string;
  s3Key?: string;
  id?: string;
  title: string;
  fileName: string;
  isDuplicate: boolean;
}
