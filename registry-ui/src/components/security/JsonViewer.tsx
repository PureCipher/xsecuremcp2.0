"use client";

import { useState } from "react";

import { Accordion, AccordionDetails, AccordionSummary, Box, Typography } from "@mui/material";

export function JsonViewer({
  data,
  title,
  defaultExpanded = false,
}: {
  data: unknown;
  title?: string;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <Accordion
      expanded={expanded}
      onChange={(_, next) => setExpanded(next)}
      elevation={0}
      sx={{
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        backgroundImage: "none",
        "&:before": { display: "none" },
      }}
    >
      <AccordionSummary
        sx={{
          minHeight: 44,
          "& .MuiAccordionSummary-content": { my: 1 },
        }}
      >
        <Typography sx={{ fontSize: 12, fontWeight: 700, color: "var(--app-muted)" }}>
          {title || "Raw JSON"}
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        <Box
          component="pre"
          sx={{
            maxHeight: 360,
            overflow: "auto",
            m: 0,
            p: 1.5,
            borderRadius: 2,
            border: "1px solid var(--app-border)",
            bgcolor: "var(--app-surface)",
            color: "var(--app-fg)",
            fontSize: 11,
            lineHeight: 1.5,
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          }}
        >
          {JSON.stringify(data, null, 2)}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
