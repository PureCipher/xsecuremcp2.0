import { allowedRegistryOrigin, defaultRegistryMcpUrl } from "@/lib/secureCliOrigin";

import { CliPageClient } from "./CliPageClient";

export default function RegistryCliPage() {
  const mcpUrl = defaultRegistryMcpUrl();
  const origin = allowedRegistryOrigin();

  return <CliPageClient defaultMcpUrl={mcpUrl} allowedOrigin={origin} />;
}
