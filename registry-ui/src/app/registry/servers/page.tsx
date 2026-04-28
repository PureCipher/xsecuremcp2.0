import { redirect } from "next/navigation";

/**
 * Iter 14.26 — ``/registry/servers`` is now a redirect to
 * ``/registry/publishers``. The two pages were rendering the same
 * publisher list with different chrome; the differentiation lived
 * only in the per-detail governance tabs, which now render on the
 * publisher detail page directly. Keeping the route alive as a
 * 308 redirect preserves any bookmarks / external links / older
 * notification ``link_path`` values that point here.
 */
export default function ServersPageRedirect() {
  redirect("/registry/publishers");
}

