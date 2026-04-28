import { redirect } from "next/navigation";

/**
 * Iter 14.28 — ``/public/servers/{id}`` redirects to
 * ``/public/publishers/{id}``. The public publisher detail page
 * now renders the same ``PublicServerDetailTabs`` (sanitized
 * governance + observability) below its profile cards.
 */
export default async function PublicServerDetailRedirect(props: {
  params: Promise<{ serverId: string }>;
}) {
  const { serverId } = await props.params;
  redirect(`/public/publishers/${encodeURIComponent(serverId)}`);
}
