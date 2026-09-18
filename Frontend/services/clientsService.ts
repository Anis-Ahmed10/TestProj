import {
  Client,
  GetClientResponse,
  UpdateClientBody,
  UpdateClientResponse,
  DeleteClientResponse,
  ClientCreateApiResponse,
  ClientCreateRequestPayload,
  ClientListApiResponse,
} from "@/types/client";
import {
  buildClientFieldErrors,
  buildClientRequestPayload,
  clientServiceError,
  getFriendlyClientBackendErrorMessage,
  isClientApiErrorResponse,
  mapBackendClientToClient,
} from "@/utils/clients/clientsHelpers";
import {
  apiRequest,
  type ApiErrorContext,
} from "@/utils/apiRequest/apiRequest";

const CLIENTS_ENDPOINT = "/api/v1/clients";

type ClientOperation = "fetch" | "create" | "get" | "patch" | "delete";

function clientError(operation: ClientOperation, withFieldErrors = false) {
  return ({ response, body }: ApiErrorContext): Error =>
    clientServiceError({
      message: getFriendlyClientBackendErrorMessage(
        response,
        (body ?? null) as Parameters<
          typeof getFriendlyClientBackendErrorMessage
        >[1],
        operation,
      ),
      code: isClientApiErrorResponse(body) ? body.error?.code : undefined,
      status: response?.status,
      fieldErrors: withFieldErrors
        ? buildClientFieldErrors(isClientApiErrorResponse(body) ? body : null)
        : undefined,
    });
}

export async function fetchClients(): Promise<Client[]> {
  const res = await apiRequest<ClientListApiResponse>(CLIENTS_ENDPOINT, {
    method: "GET",
    cache: "no-store",
    mapError: clientError("fetch"),
  });
  return res.data.items.map(mapBackendClientToClient);
}

export async function createClient(
  payload: ClientCreateRequestPayload,
): Promise<Client> {
  const res = await apiRequest<ClientCreateApiResponse>(CLIENTS_ENDPOINT, {
    method: "POST",
    body: JSON.stringify(buildClientRequestPayload(payload)),
    mapError: clientError("create", true),
  });
  return mapBackendClientToClient(res.data);
}

export async function getClientByName(clientName: string): Promise<Client> {
  const res = await apiRequest<GetClientResponse>(
    `${CLIENTS_ENDPOINT}/${encodeURIComponent(clientName)}`,
    { method: "GET", mapError: clientError("get") },
  );
  return mapBackendClientToClient(res.data);
}

export async function updateClientByName(
  clientName: string,
  body: UpdateClientBody,
): Promise<Client> {
  const res = await apiRequest<
    UpdateClientResponse & { data?: GetClientResponse["data"] }
  >(`${CLIENTS_ENDPOINT}/${encodeURIComponent(clientName)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
    mapError: clientError("patch"),
  });

  if (res.data) {
    return mapBackendClientToClient(res.data);
  }
  return getClientByName(clientName);
}

export async function deleteClientByName(clientName: string): Promise<void> {
  await apiRequest<DeleteClientResponse>(
    `${CLIENTS_ENDPOINT}/${encodeURIComponent(clientName)}`,
    { method: "DELETE", mapError: clientError("delete") },
  );
}
