import {
  ALL_INDUSTRIES,
  CLIENT_INDUSTRY_OPTIONS,
  Client,
  ClientApiErrorResponse,
  ClientBackendRecord,
  ClientCreateRequestPayload,
  ClientFormErrors,
  ClientFormValues,
  ClientStatus,
  GetClientResponse,
  IndustryType,
  UpdateClientResponse,
  DeleteClientResponse,
} from "@/types/client";

const STATUS_ALIASES: Record<string, ClientStatus> = {
  active: "On Track",
  ontrack: "On Track",
  healthy: "On Track",
  atrisk: "At Risk",
  attention: "Attention",
  warning: "Attention",
  "on track": "On Track",
  "at risk": "At Risk",
};

const STATUS_PROGRESS: Record<ClientStatus, number> = {
  "On Track": 70, // healthy, shown as majority-filled
  "At Risk": 38, // degraded, shown as minority-filled
  Attention: 52, // warning, shown between the two
};

const STATUS_CLASS_NAMES: Record<
  ClientStatus,
  { progress: string; pill: string }
> = {
  "On Track": {
    progress: "client-card__progress-fill--on-track",
    pill: "status-pill--on-track",
  },
  "At Risk": {
    progress: "client-card__progress-fill--at-risk",
    pill: "status-pill--at-risk",
  },
  Attention: {
    progress: "client-card__progress-fill--attention",
    pill: "status-pill--attention",
  },
};

function toNumber(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeText(value: unknown): string {
  return typeof value === "string" ? value.trim() : String(value ?? "").trim();
}

export function normalizeClientStatus(value: string): ClientStatus {
  const normalized = normalizeText(value).toLowerCase();
  return STATUS_ALIASES[normalized] ?? "On Track";
}

export function normalizeIndustry(value: string): IndustryType {
  const normalized = normalizeText(value);
  return (normalized || CLIENT_INDUSTRY_OPTIONS[0]) as IndustryType;
}

export function formatClientLastModified(
  value: string | Date | null | undefined,
): string {
  if (!value) {
    return "Updated recently";
  }

  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Updated recently";
  }

  const today = new Date();
  const sameDay =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();

  if (sameDay) {
    return "Updated today";
  }

  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const sameYesterday =
    date.getFullYear() === yesterday.getFullYear() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getDate() === yesterday.getDate();

  if (sameYesterday) {
    return "Updated yesterday";
  }

  const day = new Intl.DateTimeFormat(undefined, { day: "numeric" }).format(
    date,
  );
  const month = new Intl.DateTimeFormat(undefined, { month: "short" }).format(
    date,
  );
  const year =
    date.getFullYear() === today.getFullYear() ? "" : ` ${date.getFullYear()}`;

  return `Updated ${day} ${month}${year}`;
}

export function buildClientRequestPayload(
  values: ClientFormValues,
): ClientCreateRequestPayload {
  return {
    name: values.name.trim(),
    industry: values.industry,
    location: values.location.trim(),
    contact: values.contact.trim(),
    manager: values.manager?.trim(),
  };
}

export function mapBackendClientToClient(record: ClientBackendRecord): Client {
  const status = normalizeClientStatus(record.status);
  const programmesCount = toNumber(record.programmes_count);
  const projectsCount = toNumber(record.projects_count);
  const activeMembersCount = toNumber(record.active_members_count);

  // const rawManager =
  //   record.manager_name ?? (record.manager_id ? String(record.manager_id) : "");

  return {
    id: String(record.id),
    name: normalizeText(record.name),
    industry: normalizeIndustry(record.industry),
    location: normalizeText(record.location) || "Unknown",
    contact: normalizeText(record.contact),
    manager: normalizeText(record.manager_name ?? ""),
    status,
    programmesCount,
    projectsCount,
    activeMembersCount,
    lastModified: formatClientLastModified(record.last_modified),
    progress: STATUS_PROGRESS[status],
    programmes: (record.programs ?? []).map((p) => ({
      id: String(p.id),
      name: p.name,
      projects: [],
    })),
  };
}

export function buildClientFieldErrors(
  payload: ClientApiErrorResponse | null,
): ClientFormErrors | null {
  const code = payload?.error?.code?.toUpperCase();

  if (code === "CLIENT_ALREADY_EXISTS") {
    return {
      name: "A Client with this name already exists.",
    };
  }

  return null;
}

export function isClientApiErrorResponse(
  payload: unknown,
): payload is ClientApiErrorResponse {
  if (!payload || typeof payload !== "object") return false;
  if (!("error" in payload)) return false;
  const err = (payload as Record<string, unknown>).error;
  return (
    typeof err === "object" &&
    err !== null &&
    ("code" in err || "message" in err)
  );
}

type ClientErrorLikePayload =
  | ClientApiErrorResponse
  | GetClientResponse
  | UpdateClientResponse
  | DeleteClientResponse
  | null;

export function getFriendlyClientBackendErrorMessage(
  response: Response | null,
  payload: ClientErrorLikePayload,
  operation: "fetch" | "create" | "get" | "patch" | "delete",
): string {
  if (!response) {
    return "Unable to reach the backend. Please ensure the backend is running.";
  }

  const code = (
    payload as ClientApiErrorResponse | null
  )?.error?.code?.toUpperCase();

  const backendMessage =
    (payload as ClientApiErrorResponse | null)?.error?.message ??
    payload?.message;

  const isListLike = operation === "fetch" || operation === "get";
  const isMutationLike =
    operation === "create" || operation === "patch" || operation === "delete";

  const codeMessageMap: Record<string, string> = {
    INVALID_JSON:
      "The client service could not read the request. Please try again with valid data.",
    INVALID_INPUT:
      "The client details are not valid. Please review the form and try again.",
    NOT_FOUND:
      "The client endpoint could not be found. Please verify the backend URL.",
    HTTP_ERROR: isListLike
      ? "The backend returned an error while loading the client(s). Please try again."
      : "The backend returned an error while updating the client. Please try again.",
    CLIENT_ALREADY_EXISTS: "A Client with this name already exists.",
    CLIENT_CREATE_FAILED:
      "Unable to create the client right now. Please try again shortly.",
    CLIENT_LIST_FAILED:
      "Unable to load clients right now. Please try again shortly.",
    INTERNAL_SERVER_ERROR: isListLike
      ? "The backend is currently unable to load clients. Please try again shortly."
      : "The backend is currently unable to update clients. Please try again shortly.",
  };
  if (
    operation === "patch" &&
    code === "INVALID_INPUT" &&
    backendMessage &&
    /already\s+exist|already\s+exists|name\s+already|duplicate/i.test(
      backendMessage,
    )
  ) {
    return "Client name already exists";
  }

  if (code && codeMessageMap[code]) {
    return codeMessageMap[code];
  }

  if (response.status === 404) {
    return "The client endpoint could not be found. Please verify the backend URL.";
  }

  if (response.status >= 500) {
    if (operation === "fetch" || operation === "get") {
      return "The backend is currently unable to load clients. Please try again shortly.";
    }

    return "The backend is currently unable to update clients. Please try again shortly.";
  }

  if (backendMessage) {
    return backendMessage;
  }

  if (isListLike) {
    return "Backend rejected the client request.";
  }

  if (isMutationLike) {
    return "Backend rejected the client update request.";
  }

  return "Backend rejected the request.";
}

export function isClientServiceError(error: unknown): error is Error & {
  code?: string;
  status?: number;
  fieldErrors?: ClientFormErrors;
} {
  return (
    typeof error === "object" &&
    error !== null &&
    error instanceof Error &&
    "fieldErrors" in error
  );
}

export function clientServiceError(args: {
  message: string;
  code?: string;
  status?: number;
  fieldErrors?: ClientFormErrors | null;
}): Error & {
  code?: string;
  status?: number;
  fieldErrors?: ClientFormErrors;
} {
  const error = new Error(args.message) as Error & {
    code?: string;
    status?: number;
    fieldErrors?: ClientFormErrors;
  };

  error.code = args.code;
  error.status = args.status;
  error.fieldErrors = args.fieldErrors ?? undefined;

  return error;
}

export function getEmptyClientFormValues(): ClientFormValues {
  return {
    name: "",
    industry: "University",
    location: "",
    contact: "",
  };
}

export function isAllIndustries(value: string): value is typeof ALL_INDUSTRIES {
  return value === ALL_INDUSTRIES;
}

export function getClientStatusClassNames(status: ClientStatus): {
  progress: string;
  pill: string;
} {
  return STATUS_CLASS_NAMES[status];
}
