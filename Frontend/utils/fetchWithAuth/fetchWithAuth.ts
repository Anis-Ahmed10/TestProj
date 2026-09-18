import { fetchAuthSession } from "aws-amplify/auth";

export class UnauthenticatedError extends Error {
  readonly name = "UnauthenticatedError" as const;
  constructor() {
    super("Unauthenticated");
  }
}

export class ForbiddenError extends Error {
  readonly name = "ForbiddenError" as const;
  constructor(message?: string) {
    super(message || "You do not have permission to perform this action.");
  }
}

let tokenPromise: Promise<string | undefined> | null = null;

async function getToken(): Promise<string | undefined> {
  if (!tokenPromise) {
    tokenPromise = fetchAuthSession()
      .then((s) => s.tokens?.idToken?.toString())
      .finally(() => {
        tokenPromise = null;
      });
  }
  return tokenPromise;
}

function redirectToLogin(): never {
  window.location.replace("/login");
  throw new UnauthenticatedError();
}

export async function fetchWithAuth(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  if (typeof window === "undefined") {
    throw new Error("fetchWithAuth called outside browser context");
  }

  let token: string | undefined;
  try {
    token = await getToken();
  } catch {
    return redirectToLogin();
  }

  if (!token) {
    return redirectToLogin();
  }

  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(input, { ...init, headers });

  if (response.status === 401) {
    return redirectToLogin();
  }

  if (response.status === 403) {
    const message = await response
      .clone()
      .json()
      .then((body) => body?.error?.message as string | undefined)
      .catch(() => undefined);
    throw new ForbiddenError(message);
  }

  return response;
}
