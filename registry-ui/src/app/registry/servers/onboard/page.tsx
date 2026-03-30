import { listPublishers, type PublisherSummary } from "@/lib/registryClient";

import { ServerOnboardWizard } from "./ServerOnboardWizard";

export default async function OnboardServerPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  const servers = publishers.map((p) => ({
    publisherId: p.publisher_id,
    displayName: p.display_name ?? p.publisher_id,
    toolCount: p.tool_count ?? 0,
  }));

  return <ServerOnboardWizard servers={servers} />;
}

