import { getProvenanceRecords, getProvenanceChainStatus } from "@/lib/registryClient";
import { ProvenanceDashboard } from "./ProvenanceDashboard";

export const dynamic = "force-dynamic";

export default async function ProvenancePage() {
  const [recordsResp, chainStatus] = await Promise.all([
    getProvenanceRecords({ limit: 200 }),
    getProvenanceChainStatus(),
  ]);

  const records = recordsResp?.records ?? [];

  return (
    <div>
      <ProvenanceDashboard records={records} chainStatus={chainStatus} />
    </div>
  );
}
