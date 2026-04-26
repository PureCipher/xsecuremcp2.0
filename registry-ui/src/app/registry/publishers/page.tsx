import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";
import { listPublishers, type PublisherSummary } from "@/lib/registryClient";
import { PublishersDirectory } from "./PublishersDirectory";

export default async function PublishersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Publisher directory"
        title="People and teams behind the tools"
        description="Browse publishers with live listings in the registry. Open any profile to see their tools and trust signals."
      />

      <PublishersDirectory publishers={publishers} toolsHref="/registry/app" publishHref="/registry/publish" />
    </Box>
  );
}
