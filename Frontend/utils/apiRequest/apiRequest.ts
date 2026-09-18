import {
  fetchWithAuth,
  ForbiddenError,
  UnauthenticatedError,
} from "@/utils/fetchWithAuth/fetchWithAuth";

/** Error thrown by {@link apiRequest} for a non-2xx (or `success: false`) backend response. */
export class ServiceError extends Error {
  readonly name = "ServiceError" as const;
  code?: string;
  status?: number;

  constructor(message: string, opts?: { code?: string; status?: number }) {
    super(message);
    this.code = opts?.code;
    this.status = opts?.status;
  }
}

export type ApiErrorContext = {
  response: Response | null;
  body: unknown;
  cause?: unknown;
};

export type ApiRequestOptions = RequestInit & {
  mapError?: (ctx: ApiErrorContext) => Error;
  isError?: (body: unknown) => boolean;
  lambda?: boolean;
};

const INVALID_JSON = { success: false };

function resolveBaseUrl(lambda: boolean): string {
  const url = lambda
    ? process.env.NEXT_PUBLIC_LAMBDA_URL ||
      process.env.NEXT_PUBLIC_BACKEND_API_URL
    : process.env.NEXT_PUBLIC_BACKEND_API_URL;
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_BACKEND_API_URL is not configured. Set it in your .env file.",
    );
  }
  return url;
}

function defaultIsError(body: unknown): boolean {
  return (
    typeof body === "object" &&
    body !== null &&
    (body as { success?: unknown }).success === false
  );
}

function defaultError(response: Response, body: unknown): ServiceError {
  const b = (typeof body === "object" && body ? body : {}) as {
    error?: { code?: unknown; message?: unknown };
    detail?: unknown;
    message?: unknown;
  };
  const message =
    (typeof b.error?.message === "string" && b.error.message) ||
    (typeof b.detail === "string" && b.detail) ||
    (typeof b.message === "string" && b.message) ||
    `Request failed (${response.status})`;
  const code = typeof b.error?.code === "string" ? b.error.code : undefined;
  return new ServiceError(message, { code, status: response.status });
}

export async function apiRequest<T>(
  path: string,
  opts: ApiRequestOptions = {},
): Promise<T> {
  const { mapError, isError, lambda = false, headers, ...init } = opts;
  const url = `${resolveBaseUrl(lambda)}${path}`;

  let response: Response;
  try {
    const mergedHeaders = new Headers(headers);
    if (!mergedHeaders.has("Accept")) {
      mergedHeaders.set("Accept", "application/json");
    }

    if (typeof init.body === "string" && !mergedHeaders.has("Content-Type")) {
      mergedHeaders.set("Content-Type", "application/json");
    }
    response = await fetchWithAuth(url, { ...init, headers: mergedHeaders });
  } catch (cause) {
    if (
      cause instanceof UnauthenticatedError ||
      cause instanceof ForbiddenError
    ) {
      throw cause;
    }
    // A cancelled request is not a service failure, so it must not be dressed up
    // as one. AbortSignal.timeout() raises TimeoutError instead, leaving genuine
    // timeouts to mapError.
    if (cause instanceof Error && cause.name === "AbortError") throw cause;
    if (mapError) throw mapError({ response: null, body: null, cause });
    throw cause instanceof Error
      ? cause
      : new ServiceError("Network request failed");
  }

  const raw = await response.text().catch(() => "");
  let body: unknown = null;
  if (raw) {
    try {
      body = JSON.parse(raw);
    } catch {
      body = INVALID_JSON;
    }
  }

  // 204/205/304 carry no content by definition; any other status with an empty
  // body is a truncated or proxied response, so fail here rather than hand the
  // caller a null to dereference.
  const emptyBody =
    !raw &&
    response.status !== 204 &&
    response.status !== 205 &&
    response.status !== 304;

  // The sentinel fails even when a caller opts out of body checks: a non-empty
  // body we cannot parse is never a usable result.
  const failed =
    !response.ok ||
    emptyBody ||
    body === INVALID_JSON ||
    (isError ?? defaultIsError)(body);

  if (failed) {
    if (mapError) throw mapError({ response, body });
    throw emptyBody
      ? new ServiceError("Empty response from server", {
          status: response.status,
        })
      : defaultError(response, body);
  }

  return body as T;
}
