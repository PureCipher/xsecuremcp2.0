export function normalizeRegistryLanding(value: string | undefined): string | null {
  if (!value?.startsWith("/registry/")) return null;
  if (value.includes("://") || value.includes("\\")) return null;
  return value;
}

export function defaultRegistryLandingForRole(role: string | null | undefined): string {
  if (role === "publisher") return "/registry/publish/mine";
  if (role === "reviewer") return "/registry/review";
  return "/registry/app";
}

export function resolveRegistryLanding(
  preferredLanding: string | undefined,
  role: string | null | undefined,
): string {
  return normalizeRegistryLanding(preferredLanding) ?? defaultRegistryLandingForRole(role);
}
