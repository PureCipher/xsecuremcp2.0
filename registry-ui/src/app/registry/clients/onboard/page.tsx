import { listPublishers, type PublisherSummary } from "@/lib/registryClient";

import { ClientOnboardWizard } from "./ClientOnboardWizard";

export default async function OnboardClientPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  const servers = publishers.map((p) => ({
    serverId: p.publisher_id,
    displayName: p.display_name ?? p.publisher_id,
    toolCount: p.tool_count ?? 0,
  }));

  return <ClientOnboardWizard servers={servers} />;
}

