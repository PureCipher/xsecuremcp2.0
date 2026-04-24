/** RBAC persona mirrored from `RegistryRole` + dev "open" when registry auth is off. */

export type RegistryPersonaId = "viewer" | "publisher" | "reviewer" | "admin" | "open";

export function registryPersonaFromSession(
  authEnabled: boolean,
  role: string | null | undefined,
): RegistryPersonaId {
  if (!authEnabled) {
    return "open";
  }
  if (role === "viewer" || role === "publisher" || role === "reviewer" || role === "admin") {
    return role;
  }
  return "viewer";
}
