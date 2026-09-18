export const AVATAR_COLORS = [
  "#1f5c54",
  "#2563eb",
  "#7c3aed",
  "#b45309",
  "#0e7490",
  "#be185d",
  "#15803d",
  "#c2410c",
  "#4338ca",
  "#0f766e",
];

export function getAvatarColor(name?: string | null): string {
  const code = (name ?? "").charCodeAt(0) + ((name ?? "").charCodeAt(1) || 0);
  return AVATAR_COLORS[code % AVATAR_COLORS.length];
}

export function getInitials(name?: string | null): string {
  return (name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function getRoleTagColor(role?: string | null): string {
  const lower = (role ?? "").toLowerCase();
  if (lower.includes("admin")) return "gold";
  if (lower.includes("lead")) return "blue";
  if (lower.includes("engineer")) return "volcano";
  if (lower.includes("manager")) return "magenta";
  return "default";
}
