import { redirect } from "next/navigation";

import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

import {
  getReviewQueue,
  requireReviewerRole,
} from "@/lib/registryClient";
import { ReviewQueueClient } from "./ReviewQueueClient";

export default async function ReviewPage() {
  const { allowed } = await requireReviewerRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  const queue = (await getReviewQueue()) ?? {};

  if (queue.error) {
    redirect("/registry/app");
  }

  const sections = queue.sections ?? {};

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Moderation queue"
        title="Review shared tools"
        description="Approve, reject, or pause tools before they appear in the public catalog."
      />

      <ReviewQueueClient sections={sections} />
    </Box>
  );
}
