import {
  getReviewQueue,
  type ReviewQueueItem,
} from "@/lib/registryClient";
import { CertificationBadge } from "@/components/security";
import { ReviewActions } from "./ReviewActions";

function sectionLabel(key: string): string {
  if (key === "pending_review") return "Waiting for approval";
  if (key === "published") return "Live tools";
  if (key === "suspended") return "Paused tools";
  return key;
}

export default async function ReviewPage() {
  const queue = (await getReviewQueue()) ?? {};

  // If backend returned an error (e.g., 401/403), show that message.
  if (queue.error) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-base font-semibold text-[--app-fg]">Moderation queue</h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">{queue.error}</p>
      </div>
    );
  }

  const sections: Record<string, ReviewQueueItem[]> = queue.sections ?? {};

  return (
    <div className="flex flex-col gap-6">
        <header className="flex flex-col gap-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Moderation queue
          </p>
          <h1 className="text-2xl font-semibold text-[--app-fg]">Review shared tools</h1>
          <p className="mt-1 max-w-xl text-[11px] text-[--app-muted]">
            Approve, reject, or pause tools before they appear in the public catalog.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          {["pending_review", "published", "suspended"].map((key) => {
            const items = sections[key] ?? [];
            return (
              <div
                key={key}
                className="flex min-h-[220px] flex-col gap-3 rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]"
              >
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                    {sectionLabel(key)}
                  </h2>
                  <p className="mt-1 text-[10px] text-[--app-muted]">
                    {items.length} listing{items.length === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="flex flex-1 flex-col gap-3 overflow-auto">
                  {items.length === 0 ? (
                    <p className="text-[11px] text-[--app-muted]">Nothing in this lane right now.</p>
                  ) : (
                    items.map((item) => {
                      const log = Array.isArray(item.moderation_log)
                        ? item.moderation_log[item.moderation_log.length - 1]
                        : null;
                      const reason = log?.reason ?? "";
                      return (
                        <article
                          key={item.listing_id}
                          className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-3 ring-1 ring-[--app-surface-ring]"
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <div>
                              <h3 className="text-[12px] font-semibold text-[--app-fg]">
                                {item.display_name ?? item.tool_name}
                              </h3>
                              <p className="text-[10px] text-[--app-muted]">
                                {item.tool_name} · {item.version}
                              </p>
                            </div>
                            <CertificationBadge level={item.certification_level} />
                          </div>
                          <p className="mt-1 line-clamp-3 text-[11px] leading-relaxed text-[--app-muted]">
                            {item.description ?? "No description provided."}
                          </p>
                          {log ? (
                            <p className="mt-1 text-[10px] text-[--app-muted]">
                              Last decision:{" "}
                              <span className="font-semibold">{log.action}</span> by{" "}
                              <span className="font-mono text-[--app-muted]">{log.moderator_id}</span>
                              {reason ? <> — {reason.slice(0, 80)}{reason.length > 80 ? "…" : ""}</> : null}
                            </p>
                          ) : null}
                          <ReviewActions
                            listingId={item.listing_id}
                            availableActions={item.available_actions ?? []}
                          />
                        </article>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </section>
    </div>
  );
}
