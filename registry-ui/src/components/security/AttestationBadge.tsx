import { Chip, Tooltip } from "@mui/material";

/**
 * Visualizes the *kind* of trust signal carried by a listing.
 *
 * The certification level (Self-attested → Strict) describes how
 * thorough the manifest review was. The attestation kind describes
 * **who is making the claim** — the original author, or a registry
 * curator vouching for someone else's server. Both signals are
 * orthogonal and matter independently when a visitor is deciding
 * whether to install.
 *
 * - ``author``  → "Author-attested" (default; understated styling).
 * - ``curator`` → "Curator-vouched" (explicit accent border + the
 *   curator's username when known, so the visitor can tell who is
 *   making the claim).
 * - missing / unknown → renders nothing.
 */

type AttestationKind = "author" | "curator" | string | undefined;

type Props = {
  kind: AttestationKind;
  curatorId?: string | null;
  size?: "sm" | "md";
  /** When true, the author-attested case ALSO renders a chip — useful
   *  on detail pages where you want to surface both kinds explicitly.
   *  Defaults to false (catalog cards only need the curator chip). */
  showAuthor?: boolean;
};

export function AttestationBadge({
  kind,
  curatorId,
  size = "sm",
  showAuthor = false,
}: Props) {
  const height = size === "md" ? 24 : 22;
  if (kind === "curator") {
    const label = curatorId ? `Curator-vouched · ${curatorId}` : "Curator-vouched";
    const tooltip =
      "Vouched for by a third-party PureCipher curator. The curator " +
      "observed the upstream and signed an attestation; the original " +
      "author is unaware of and unaffected by this listing.";
    return (
      <Tooltip title={tooltip} placement="top" arrow>
        <Chip
          size="small"
          label={label}
          sx={{
            borderRadius: 2,
            height,
            bgcolor: "rgba(245, 158, 11, 0.12)",
            color: "#92400e",
            border: "1px solid rgba(245, 158, 11, 0.32)",
            fontSize: 11,
            fontWeight: 700,
            textTransform: "none",
            letterSpacing: "0.01em",
            "& .MuiChip-label": {
              px: size === "md" ? 1.25 : 1,
            },
          }}
        />
      </Tooltip>
    );
  }

  if (kind === "author" && showAuthor) {
    return (
      <Tooltip
        title="The original tool author submitted and signed this manifest."
        placement="top"
        arrow
      >
        <Chip
          size="small"
          label="Author-attested"
          sx={{
            borderRadius: 2,
            height,
            bgcolor: "var(--app-control-bg)",
            color: "var(--app-muted)",
            border: "1px solid var(--app-control-border)",
            fontSize: 11,
            fontWeight: 700,
            textTransform: "none",
            letterSpacing: "0.01em",
            "& .MuiChip-label": {
              px: size === "md" ? 1.25 : 1,
            },
          }}
        />
      </Tooltip>
    );
  }

  return null;
}
