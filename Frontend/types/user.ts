export interface PlatformUser {
  id: string;
  name?: string | null;
  email?: string | null;
  role?: string | null;
}

export interface PlatformRole {
  id: string;
  name: string;
  description?: string;
}

export interface ProjectApprover {
  role_label: string;
  name: string;
  email: string;
}
