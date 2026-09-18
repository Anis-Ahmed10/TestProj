const PROGRAMME_ID_KEY = "nav:activeProgrammeId";
const PROJECT_ID_KEY = "nav:activeProjectId";

function safeSet(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(key, value);
  } catch {}
}

function safeGet(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function setActiveProgrammeId(id: string): void {
  safeSet(PROGRAMME_ID_KEY, id);
}

export function getActiveProgrammeId(): string | null {
  return safeGet(PROGRAMME_ID_KEY);
}

export function setActiveProjectId(id: string): void {
  safeSet(PROJECT_ID_KEY, id);
}

export function getActiveProjectId(): string | null {
  return safeGet(PROJECT_ID_KEY);
}
