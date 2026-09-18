import {
  CreateProgrammeResponse,
  GetProgrammeResponse,
  Programme,
  ProgrammeBackendRecord,
  UpdateProgrammeResponse,
} from "@/types/programme";

import {
  isProgrammeApiError,
  mapBackendProgramme,
  programmeServiceError,
} from "@/utils/programmes/programmeHelpers";
import {
  apiRequest,
  type ApiErrorContext,
} from "@/utils/apiRequest/apiRequest";

function programmeError(action: string, networkFallback: string) {
  return ({ response, body, cause }: ApiErrorContext): Error => {
    if (!response) {
      return programmeServiceError({
        message: cause instanceof Error ? cause.message : networkFallback,
      });
    }
    const backendMessage = isProgrammeApiError(body)
      ? body.error?.message ?? body.message
      : undefined;
    return programmeServiceError({
      message: backendMessage ?? `${action} (HTTP ${response.status})`,
      code: isProgrammeApiError(body) ? body.error?.code : undefined,
      status: response.status,
    });
  };
}

export async function getProgrammeById(
  programmeId: string,
): Promise<Programme> {
  const body = await apiRequest<GetProgrammeResponse>(
    `/api/v1/programmes/${encodeURIComponent(programmeId)}`,
    {
      method: "GET",
      cache: "no-store",
      isError: isProgrammeApiError,
      mapError: programmeError(
        "Failed to load programme",
        "An unexpected error occurred while loading the programme.",
      ),
    },
  );
  return mapBackendProgramme(body.data);
}

export async function createProgramme(payload: {
  clientId: string;
  name: string;
  description?: string;
}): Promise<{ id: string; clientId: string; name: string }> {
  const body = await apiRequest<CreateProgrammeResponse>("/api/v1/programmes", {
    method: "POST",
    body: JSON.stringify({
      client_id: payload.clientId,
      name: payload.name,
      description: payload.description ?? null,
    }),
    isError: isProgrammeApiError,
    mapError: programmeError(
      "Failed to create programme",
      "An unexpected error occurred while creating the programme.",
    ),
  });

  const data = body.data;
  return {
    id: String(data.id),
    clientId: String(data.client_id),
    name: data.name,
  };
}

export async function updateProgrammeById(
  programmeId: string,
  payload: { name?: string; description?: string; status?: string },
): Promise<Partial<Programme>> {
  const body = await apiRequest<UpdateProgrammeResponse>(
    `/api/v1/programmes/${encodeURIComponent(programmeId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
      isError: isProgrammeApiError,
      mapError: programmeError(
        "Failed to update programme",
        "An unexpected error occurred while updating the programme.",
      ),
    },
  );

  const data = body.data;
  return {
    id: String(data.id),
    name: data.name,
    description: data.description ?? undefined,
    status: data.status ?? "active",
    lastModified: data.last_modified ?? undefined,
  };
}

export async function deleteProgrammeById(programmeId: string): Promise<void> {
  await apiRequest<unknown>(
    `/api/v1/programmes/${encodeURIComponent(programmeId)}`,
    {
      method: "DELETE",
      isError: () => false,
      mapError: programmeError(
        "Failed to delete programme",
        "An unexpected error occurred while deleting the programme.",
      ),
    },
  );
}

export async function listProgrammesByClientId(
  clientId: string,
): Promise<Programme[]> {
  const body = await apiRequest<{ data?: ProgrammeBackendRecord[] }>(
    `/api/v1/programmes?client_id=${encodeURIComponent(clientId)}`,
    {
      method: "GET",
      cache: "no-store",
      isError: isProgrammeApiError,
      mapError: programmeError(
        "Failed to load programmes",
        "An unexpected error occurred while loading programmes.",
      ),
    },
  );
  return (body.data ?? []).map((p) => mapBackendProgramme(p));
}
