import { Project, ProjectBackendRecord, ProjectFormErrors } from "./project";
export interface ProgrammeBackendRecord {
  id: string;
  client_id: string;
  name: string;
  description?: string | null;
  status: string;
  manager?: string | null;
  manager_name?: string | null;
  created_at?: string | null;
  last_modified?: string | null;
  project_count?: number;
  projects: ProjectBackendRecord[];
}

export interface Programme {
  id: string;
  clientId: string;
  name: string;
  description?: string;
  status: string;
  manager?: string;
  createdAt?: string;
  lastModified?: string;
  projects: Project[];
  projectCount?: number;
}

export interface ProgrammeApiSuccessResponse<T> {
  success: true;
  message: string;
  data: T;
}

export interface ProgrammeApiErrorResponse {
  success?: false;
  message?: string;
  error?: { code?: string; message?: string };
}

export type GetProgrammeResponse =
  ProgrammeApiSuccessResponse<ProgrammeBackendRecord>;

export type CreateProgrammeResponse = ProgrammeApiSuccessResponse<{
  id: string;
  client_id: string;
  name: string;
}>;

export type UpdateProgrammeResponse = ProgrammeApiSuccessResponse<{
  id: string;
  name: string;
  description?: string | null;
  status?: string | null;
  last_modified?: string | null;
}>;

export type ProgrammeServiceError = Error & {
  code?: string;
  status?: number;
  fieldErrors?: ProjectFormErrors;
};
