import { redirect } from "next/navigation";

/**
 * Iter 14.28 — ``/public/servers`` is a redirect to
 * ``/public/publishers``. The two pages were rendering the same
 * publisher list; the only differentiation lived in the per-server
 * detail page's ``PublicServerDetailTabs``, which now render on the
 * public publisher detail page directly. Keeping the route alive as
 * a redirect preserves any external links that point here.
 */
export default function PublicServersRedirect() {
  redirect("/public/publishers");
}
