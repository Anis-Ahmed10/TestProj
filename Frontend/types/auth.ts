export const ROLES = [
  "Admin",
  "Test Lead",
  "Test Manager",
  "Test Engineer",
] as const;

export type Role = (typeof ROLES)[number];

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  role: string;
  permissions: string[];
}

export interface MeApiResponse {
  success: true;
  message: string;
  data: CurrentUser;
}

export interface AuthApiErrorResponse {
  success: false;
  error?: { code?: string; message?: string };
}
