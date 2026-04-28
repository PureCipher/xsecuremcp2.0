import { redirect } from "next/navigation";

/**
 * Iter 14.26 — ``/registry/servers/{id}`` redirects to
 * ``/registry/publishers/{id}``. The publisher detail page now
 * renders the same ``ServerDetailTabs`` (governance + observability)
 * below its profile cards, so the previous "MCP Servers" detail
 * surface is preserved at the new URL. The redirect keeps stale
 * notification links and bookmarks working — important because
 * many of those links were minted by the moderation flow's
 * notification feed.
 */
export default async function ServerDetailRedirect(props: {
  params: Promise<{ serverId: string }>;
}) {
  const { serverId } = await props.params;
  redirect(`/registry/publishers/${encodeURIComponent(serverId)}`);
}
