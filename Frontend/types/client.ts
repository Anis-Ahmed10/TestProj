export const CLIENT_STATUS_OPTIONS = [
  "On Track",
  "At Risk",
  "Attention",
] as const;

export type ClientStatus = (typeof CLIENT_STATUS_OPTIONS)[number];

export const CLIENT_INDUSTRY_OPTIONS = [
  "University",
  "Healthcare",
  "Banking",
  "Insurance",
  "Retail",
] as const;

export type IndustryType = (typeof CLIENT_INDUSTRY_OPTIONS)[number];

export const ALL_INDUSTRIES = "All Industries";

export interface ClientProject {
  id: string;
  name: string;
  status: ClientStatus;
  testCases: number;
  passRate: number;
  openDefects: number;
  aiGenerated: number;
  team: string[];
  startDate: string;
  sprint: string;
  programme: string;
}

export interface ClientProgramme {
  id: string;
  name: string;
  projects: ClientProject[];
}

export interface Client {
  id: string;
  name: string;
  industry: IndustryType;
  location: string;
  contact: string;
  status: ClientStatus;
  manager?: string;
  programmesCount: number;
  projectsCount: number;
  activeMembersCount: number;
  lastModified: string;
  progress: number;
  programmes: ClientProgramme[];
}

export type ClientFormField = "name" | "industry" | "location" | "contact";

export interface ClientFormValues {
  name: string;
  industry: IndustryType;
  location: string;
  contact: string;
  manager?: string;
}

export type ClientCreateRequestPayload = ClientFormValues;

export interface ClientFormErrors {
  name?: string;
  industry?: string;
  location?: string;
  contact?: string;
}

export interface ClientApiErrorBody {
  code?: string;
  message?: string;
}

export interface ClientApiErrorResponse {
  success?: false;
  message?: string;
  error?: ClientApiErrorBody;
}

export interface ClientApiSuccessResponse<T> {
  success: true;
  message: string;
  data: T;
}

export interface ClientBackendRecord {
  id: string | number;
  name: string;
  industry: string;
  location?: string | null;
  contact: string;
  status: string;
  manager_name?: string;
  manager_id?: string | number;
  programmes_count?: number;
  projects_count?: number;
  active_members_count?: number;
  created_at?: string;
  last_modified?: string;
  programs?: Array<{
    id: string;
    name: string;
    description?: string | null;
  }>;
}

export interface ClientListResponseData {
  items: ClientBackendRecord[];
  total: number;
}

export type ClientListApiResponse =
  ClientApiSuccessResponse<ClientListResponseData>;

export type ClientCreateApiResponse =
  ClientApiSuccessResponse<ClientBackendRecord>;

export type ClientServiceError = Error & {
  code?: string;
  status?: number;
  fieldErrors?: ClientFormErrors;
};

export type GetClientResponse = {
  success: boolean;
  message: string;
  data: {
    id: number;
    name: string;
    industry: string;
    location: string;
    contact: string;
    status: ClientStatus;
    manager?: string;
    programmes_count: number;
    projects_count: number;
    active_members_count: number;
    programs: Array<{
      id: string;
      name: string;
      description: string;
    }>;
  };
};

export type UpdateClientBody = {
  contact?: string;
  industry?: string;
  location?: string;
  name?: string;
  status?: ClientStatus;
  manager_id?: string | null;
};

export type UpdateClientResponse = {
  success: boolean;
  message: string;
  data?: unknown;
};

export type DeleteClientResponse = {
  success: boolean;
  message: string;
  data?: unknown;
};

export type EditFormErrors = {
  name?: string;
  location?: string;
  contact?: string;
};
