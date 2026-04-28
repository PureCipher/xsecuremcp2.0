import { Box, Chip, Typography } from "@mui/material";
import type { ToolVersionItem } from "@/lib/registryClient";

/**
 * Iter 14.31 — Version history with manifest-changed indicator.
 *
 * The previous rendering was a flat list ("v1.0 · published 2024-…").
 * For a security registry, the most-asked question about a new
 * version is "did the security manifest change?" — not "was the
 * version bumped?". A version can re-publish the same manifest
 * (metadata-only update like a description tweak) or ship with a
 * brand-new manifest (new permissions, data flows, etc.). Those are
 * categorically different events from a trust standpoint.
 *
 * The backend only stores ``manifest_digest`` per version, not the
 * full manifest contents. That's enough for *this* indicator —
 * adjacent versions with different digests means the manifest
 * contents changed; identical digests mean only metadata moved.
 *
 * A future iteration can plumb per-version manifest snapshots
 * through the backend so we can render the *actual* permission
 * delta (new perms requested, data flows added, certification
 * tier changed). That's noted in the helper text below the list
 * so the curator knows the distinction.
 */
export function VersionHistory({ versions }: { versions: ToolVersionItem[] }) {
  if (versions.length === 0) {
    return (
      <Typography sx={{ mt: 1.5, fontSize: 12, color: "var(--app-muted)" }}>
        No version history available yet.
      </Typography>
    );
  }

  const visible = versions.slice(0, 12);

  return (
    <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
      {visible.map((v, idx) => {
        const previous = visible[idx + 1];
        // ``visible`` is most-recent-first. ``previous`` is the
        // next-older version, if any. If digests differ, the
        // manifest contents changed at this release.
        const manifestChanged =
          previous != null &&
          v.manifest_digest != null &&
          previous.manifest_digest != null &&
          v.manifest_digest !== previous.manifest_digest;
        const isFirstVersion = previous == null;

        return (
          <Box
            key={v.version}
            sx={{
              p: 1.5,
              borderRadius: 2,
              border: "1px solid var(--app-border)",
              bgcolor: v.yanked
                ? "rgba(253, 230, 138, 0.08)"
                : "var(--app-control-bg)",
            }}
          >
            <Box
              sx={{
                display: "flex",
                alignItems: "baseline",
                gap: 1,
                flexWrap: "wrap",
              }}
            >
              <Typography
                sx={{
                  fontSize: 13,
                  fontWeight: 800,
                  color: "var(--app-fg)",
                  fontFamily:
                    "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                }}
              >
                v{v.version}
              </Typography>

              {v.yanked ? (
                <Chip
                  size="small"
                  label={
                    v.yank_reason
                      ? `Yanked: ${v.yank_reason}`
                      : "Yanked"
                  }
                  sx={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    height: 22,
                    bgcolor: "rgba(245, 158, 11, 0.18)",
                    color: "#92400e",
                    border: "1px solid rgba(251, 191, 36, 0.4)",
                  }}
                />
              ) : null}

              {/* Iter 14.31 — manifest-change indicator. Three
                  cases:
                  - First-ever version: neutral chip ("Initial
                    manifest").
                  - Adjacent digests differ: warning chip
                    ("Manifest changed").
                  - Adjacent digests match: muted chip
                    ("Metadata only").
                  This tells the curator immediately whether each
                  version warrants a fresh security review. */}
              {isFirstVersion ? (
                <Chip
                  size="small"
                  label="Initial manifest"
                  sx={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    height: 22,
                    bgcolor: "var(--app-surface)",
                    color: "var(--app-muted)",
                    border: "1px solid var(--app-border)",
                  }}
                />
              ) : manifestChanged ? (
                <Chip
                  size="small"
                  label="Manifest changed"
                  sx={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    height: 22,
                    bgcolor: "rgba(245, 158, 11, 0.12)",
                    color: "#92400e",
                    border: "1px solid rgba(251, 191, 36, 0.4)",
                  }}
                />
              ) : (
                <Chip
                  size="small"
                  label="Metadata only"
                  sx={{
                    fontSize: 10.5,
                    fontWeight: 700,
                    height: 22,
                    bgcolor: "var(--app-surface)",
                    color: "var(--app-muted)",
                    border: "1px solid var(--app-border)",
                  }}
                />
              )}

              {v.published_at ? (
                <Typography
                  sx={{
                    fontSize: 11,
                    color: "var(--app-muted)",
                    ml: "auto",
                  }}
                >
                  {new Date(v.published_at).toLocaleString()}
                </Typography>
              ) : null}
            </Box>

            {v.changelog ? (
              <Typography
                sx={{
                  mt: 0.75,
                  fontSize: 12,
                  color: "var(--app-muted)",
                  lineHeight: 1.5,
                }}
              >
                {v.changelog}
              </Typography>
            ) : null}

            {v.manifest_digest ? (
              <Typography
                sx={{
                  mt: 0.5,
                  fontSize: 10.5,
                  color: "var(--app-muted)",
                  fontFamily:
                    "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                }}
                title={v.manifest_digest}
              >
                manifest:{v.manifest_digest.slice(0, 12)}…
              </Typography>
            ) : null}
          </Box>
        );
      })}

      {versions.length > 12 ? (
        <Typography sx={{ fontSize: 11, color: "var(--app-muted)", pl: 0.5 }}>
          +{versions.length - 12} older version{versions.length - 12 === 1 ? "" : "s"}
        </Typography>
      ) : null}

      <Typography
        sx={{
          mt: 0.5,
          fontSize: 11,
          color: "var(--app-muted)",
          fontStyle: "italic",
          lineHeight: 1.5,
        }}
      >
        &ldquo;Manifest changed&rdquo; means the signed manifest hash
        differs from the prior version — new permissions, data flows,
        or resource declarations may have been added. Compare the
        nutrition label above against the prior release before
        upgrading. Per-version manifest snapshots ship in a future
        iteration so the exact delta will be visible inline.
      </Typography>
    </Box>
  );
}
