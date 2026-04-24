import { redirect } from "next/navigation";

import { Box } from "@mui/material";

import {
  getProvenanceChainStatus,
  getProvenanceRecords,
  requireReviewerRole,
} from "@/lib/registryClient";
import { ProvenanceDashboard } from "./ProvenanceDashboard";

export const dynamic = "force-dynamic";

export default async function ProvenancePage() {
  const { allowed } = await requireReviewerRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  const [recordsResp, chainStatus] = await Promise.all([
    getProvenanceRecords({ limit: 200 }),
    getProvenanceChainStatus(),
  ]);

  const records = recordsResp?.records ?? [];

  return (
    <Box>
      <ProvenanceDashboard records={records} chainStatus={chainStatus} />
    </Box>
  );
}
