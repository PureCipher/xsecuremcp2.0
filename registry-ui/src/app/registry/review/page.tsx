import { redirect } from "next/navigation";

import { Box, Typography } from "@mui/material";

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
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Moderation queue
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Review shared tools
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
          Approve, reject, or pause tools before they appear in the public catalog.
        </Typography>
      </Box>

      <ReviewQueueClient sections={sections} />
    </Box>
  );
}
