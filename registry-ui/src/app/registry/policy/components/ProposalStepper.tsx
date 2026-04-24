"use client";

// ── Visual lifecycle stepper for policy proposals ────────────────────
// Shows the DRAFT → VALIDATED → SIMULATED → APPROVED → DEPLOYED pipeline
// with the current step highlighted and terminal states (rejected/withdrawn)
// shown as a badge overlay.

import { Box, Chip, Step, StepLabel, Stepper } from "@mui/material";

type StepDef = {
  key: string;
  label: string;
};

const STEPS: StepDef[] = [
  { key: "draft", label: "Draft" },
  { key: "validated", label: "Validated" },
  { key: "simulated", label: "Simulated" },
  { key: "approved", label: "Approved" },
  { key: "deployed", label: "Live" },
];

// Map status to the step index it corresponds to
function stepIndex(status: string | undefined): number {
  switch (status) {
    case "draft":
    case "validation_failed":
      return 0;
    case "validated":
      return 1;
    case "simulated":
      return 2;
    case "approved":
      return 3;
    case "deployed":
      return 4;
    default:
      return -1; // terminal/unknown
  }
}

function isTerminal(status: string | undefined): boolean {
  return status === "rejected" || status === "withdrawn";
}

function isFailed(status: string | undefined): boolean {
  return status === "validation_failed";
}

type ProposalStepperProps = {
  status: string | undefined;
  /** Whether simulation is required in this workspace */
  requireSimulation: boolean;
};

export function ProposalStepper({
  status,
  requireSimulation,
}: ProposalStepperProps) {
  const terminal = isTerminal(status);
  const failed = isFailed(status);

  // If simulation isn't required, skip the "Simulated" step visually
  const visibleSteps = requireSimulation
    ? STEPS
    : STEPS.filter((step) => step.key !== "simulated");

  const activeStep = (() => {
    if (terminal) return -1;
    const idx = stepIndex(status);
    const key = STEPS[idx]?.key;
    return visibleSteps.findIndex((s) => s.key === key);
  })();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Stepper
        activeStep={activeStep < 0 ? 0 : activeStep}
        alternativeLabel
        sx={{
          "& .MuiStepConnector-line": { borderColor: "var(--app-border)" },
          "& .MuiStepIcon-root.Mui-active": { color: failed ? "rgb(239, 68, 68)" : "var(--app-accent)" },
          "& .MuiStepIcon-root.Mui-completed": { color: "var(--app-accent)" },
        }}
      >
        {visibleSteps.map((step) => (
          <Step key={step.key} completed={!terminal && activeStep > visibleSteps.findIndex((s) => s.key === step.key)}>
            <StepLabel>{step.label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {terminal ? (
        <Chip
          size="small"
          label={status === "rejected" ? "Rejected" : "Withdrawn"}
          sx={{
            width: "fit-content",
            borderRadius: 999,
            bgcolor:
              status === "rejected" ? "rgba(244, 63, 94, 0.18)" : "rgba(161, 161, 170, 0.18)",
            color:
              status === "rejected" ? "rgb(254, 205, 211)" : "rgb(228, 228, 231)",
            border: "1px solid var(--app-border)",
            fontWeight: 900,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            fontSize: 10,
          }}
        />
      ) : null}
    </Box>
  );
}
