"use client";

import { useState } from "react";
import {
  Box,
  Button,
  Chip,
  Popover,
  Typography,
} from "@mui/material";
import { CertificationBadge } from "@/components/security";

/**
 * Iter 14.32 — Certification tier explainer.
 *
 * The CertificationBadge today is a passive chip ("Strict",
 * "Standard", etc.). For a security registry, the tier is the
 * single most-asked-about element on the page — but clicking it
 * does nothing, so the badge is opaque to anyone who doesn't
 * already know what each tier means.
 *
 * This component wraps the existing CertificationBadge in a
 * clickable popover. Click the badge → see what the tier requires.
 * Closes the loop: badge → meaning. Doesn't change the underlying
 * CertificationBadge component (still a pure chip), so existing
 * server-rendered call sites elsewhere keep working.
 */

type TierInfo = {
  label: string;
  oneLine: string;
  requirements: string[];
  audience: string;
};

const TIER_TABLE: Record<string, TierInfo> = {
  unrated: {
    label: "Unrated",
    oneLine:
      "The publisher has not requested certification. The manifest may still be signed, but no automated checks ran against it.",
    requirements: [
      "No certification pipeline run",
      "Trust signal limited to publisher attestation",
    ],
    audience:
      "Tools you've vetted yourself or pulled from a publisher you already trust.",
  },
  "self-attested": {
    label: "Self-attested",
    oneLine:
      "The publisher signed the manifest and asserts its accuracy. The registry verified the signature but did not score the manifest.",
    requirements: [
      "Manifest signed by the publisher",
      "Signature verified by the registry on every page load",
      "No automated safety scoring",
    ],
    audience:
      "Internal tools and trial integrations where the publisher is the source of truth.",
  },
  basic: {
    label: "Basic",
    oneLine:
      "Manifest signed and passes the registry's smoke checks: no obviously dangerous permission combinations, declared data flows for any external endpoint.",
    requirements: [
      "Manifest signed and signature verified",
      "Permissions declared explicitly (not blanket allow-all)",
      "Every external destination appears in a data_flow declaration",
      "No subprocess_exec without a corresponding command-arg schema",
    ],
    audience:
      "General-purpose tools used in non-sensitive contexts.",
  },
  standard: {
    label: "Standard",
    oneLine:
      "Basic checks plus structured review: at least one human reviewer attestation and a passing automated certification run.",
    requirements: [
      "All Basic requirements",
      "≥1 reviewer attestation present in moderation log",
      "Certification pipeline run with no critical findings",
      "Resource access declarations cover all touched URIs",
    ],
    audience:
      "Production integrations and shared internal tooling.",
  },
  strict: {
    label: "Strict",
    oneLine:
      "Standard checks plus tightest controls: dual-reviewer attestation, no elevated capabilities without explicit justification, automated revocation triggers.",
    requirements: [
      "All Standard requirements",
      "Dual-reviewer attestation (two independent approvals)",
      "Elevated permissions (subprocess_exec, file_system_write) require justification metadata",
      "Reflexive Core monitoring engaged for behavior drift",
      "Automatic suspension on signature mismatch",
    ],
    audience:
      "Compliance-sensitive deployments — GDPR, HIPAA, SOC 2, PCI-DSS contexts.",
  },
};

function tierKeyFor(level: string | undefined): string | null {
  if (!level) return null;
  const trimmed = level.trim().toLowerCase();
  if (!trimmed || trimmed === "none" || trimmed === "unknown") {
    return "unrated";
  }
  if (TIER_TABLE[trimmed]) return trimmed;
  // Heuristic match for variants ("certified-standard" → "standard"
  // etc.) so we surface something useful even if the backend ships
  // a hyphenated tier name.
  for (const key of Object.keys(TIER_TABLE)) {
    if (trimmed.includes(key)) return key;
  }
  return null;
}

export function CertificationTierExplainer({
  level,
  size = "md",
}: {
  level?: string;
  size?: "sm" | "md";
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const tierKey = tierKeyFor(level);
  const info = tierKey ? TIER_TABLE[tierKey] : null;

  const handleOpen = (e: React.MouseEvent<HTMLElement>) => {
    setAnchor(e.currentTarget);
  };
  const handleClose = () => {
    setAnchor(null);
  };

  return (
    <>
      <Box
        component="button"
        type="button"
        onClick={handleOpen}
        aria-label={`What does the ${info?.label ?? "certification"} tier mean?`}
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.5,
          background: "none",
          border: "none",
          p: 0,
          cursor: "pointer",
          borderRadius: 1.5,
          "&:hover": { opacity: 0.85 },
          "&:focus-visible": {
            outline: "2px solid var(--app-accent)",
            outlineOffset: 2,
          },
        }}
      >
        <CertificationBadge level={level} size={size} />
        <Box
          component="span"
          aria-hidden
          sx={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 16,
            height: 16,
            borderRadius: "50%",
            bgcolor: "var(--app-control-bg)",
            border: "1px solid var(--app-border)",
            color: "var(--app-muted)",
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          ?
        </Box>
      </Box>

      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={handleClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{
          paper: {
            sx: {
              maxWidth: 380,
              border: "1px solid var(--app-border)",
              boxShadow: "0 14px 38px rgba(15, 23, 42, 0.12)",
              borderRadius: 3,
            },
          },
        }}
      >
        <Box sx={{ p: 2.5 }}>
          {info ? (
            <>
              <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, mb: 1 }}>
                <Typography
                  sx={{
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "var(--app-muted)",
                  }}
                >
                  Certification tier
                </Typography>
                <Chip
                  size="small"
                  label={info.label}
                  sx={{
                    fontSize: 11,
                    fontWeight: 700,
                    height: 22,
                    bgcolor: "var(--app-control-active-bg)",
                    color: "var(--app-fg)",
                    border: "1px solid var(--app-accent)",
                  }}
                />
              </Box>

              <Typography
                sx={{
                  fontSize: 13,
                  color: "var(--app-fg)",
                  lineHeight: 1.55,
                  mb: 1.5,
                }}
              >
                {info.oneLine}
              </Typography>

              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                  mb: 0.75,
                }}
              >
                Requirements
              </Typography>
              <Box
                component="ul"
                sx={{
                  m: 0,
                  pl: 2.5,
                  display: "grid",
                  gap: 0.5,
                  fontSize: 12.5,
                  color: "var(--app-muted)",
                  lineHeight: 1.5,
                }}
              >
                {info.requirements.map((req) => (
                  <li key={req}>{req}</li>
                ))}
              </Box>

              <Typography
                sx={{
                  mt: 1.5,
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Suggested audience
              </Typography>
              <Typography
                sx={{
                  fontSize: 12.5,
                  color: "var(--app-fg)",
                  lineHeight: 1.5,
                }}
              >
                {info.audience}
              </Typography>
            </>
          ) : (
            <>
              <Typography
                sx={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: "var(--app-fg)",
                  mb: 0.5,
                }}
              >
                Custom certification level
              </Typography>
              <Typography
                sx={{ fontSize: 12.5, color: "var(--app-muted)", lineHeight: 1.5 }}
              >
                {level ? (
                  <>
                    The level{" "}
                    <Box
                      component="code"
                      sx={{
                        fontFamily:
                          "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        fontSize: 11,
                        bgcolor: "var(--app-control-bg)",
                        border: "1px solid var(--app-border)",
                        borderRadius: 1,
                        px: 0.5,
                        py: 0.125,
                      }}
                    >
                      {level}
                    </Box>{" "}
                    isn&apos;t one of the registry&apos;s standard tiers.
                    The publisher may have configured a custom certification
                    profile — check their documentation for what it means.
                  </>
                ) : (
                  <>This listing has no certification tier set.</>
                )}
              </Typography>
            </>
          )}

          <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 1.5 }}>
            <Button
              size="small"
              variant="text"
              onClick={handleClose}
              sx={{
                textTransform: "none",
                fontSize: 12,
                color: "var(--app-muted)",
              }}
            >
              Close
            </Button>
          </Box>
        </Box>
      </Popover>
    </>
  );
}
