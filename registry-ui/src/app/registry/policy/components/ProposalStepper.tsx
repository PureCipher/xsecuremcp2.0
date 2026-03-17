"use client";

// ── Visual lifecycle stepper for policy proposals ────────────────────
// Shows the DRAFT → VALIDATED → SIMULATED → APPROVED → DEPLOYED pipeline
// with the current step highlighted and terminal states (rejected/withdrawn)
// shown as a badge overlay.

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
  const currentIndex = stepIndex(status);
  const terminal = isTerminal(status);
  const failed = isFailed(status);

  // If simulation isn't required, skip the "Simulated" step visually
  const visibleSteps = requireSimulation
    ? STEPS
    : STEPS.filter((step) => step.key !== "simulated");

  // Re-map currentIndex for the visible steps
  const visibleCurrentIndex = (() => {
    if (terminal) return -1;
    const mapped = visibleSteps.findIndex(
      (step) => step.key === STEPS[currentIndex]?.key,
    );
    return mapped;
  })();

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1">
        {visibleSteps.map((step, index) => {
          const isComplete = !terminal && visibleCurrentIndex > index;
          const isCurrent = !terminal && visibleCurrentIndex === index;

          return (
            <div key={step.key} className="flex items-center gap-1">
              {/* Step dot + label */}
              <div className="flex items-center gap-1.5">
                <span
                  className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-bold ${
                    isComplete
                      ? "bg-emerald-500 text-emerald-950"
                      : isCurrent
                        ? failed
                          ? "bg-rose-500 text-rose-950 ring-2 ring-rose-400/50"
                          : "bg-emerald-400 text-emerald-950 ring-2 ring-emerald-300/50"
                        : "bg-emerald-900/50 text-emerald-400/60"
                  }`}
                >
                  {isComplete ? (
                    <svg
                      viewBox="0 0 12 12"
                      className="h-2.5 w-2.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path d="M2 6l3 3 5-5" />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </span>
                <span
                  className={`text-[10px] font-semibold ${
                    isComplete
                      ? "text-emerald-300"
                      : isCurrent
                        ? failed
                          ? "text-rose-200"
                          : "text-emerald-50"
                        : "text-emerald-400/50"
                  }`}
                >
                  {isCurrent && failed ? "Failed" : step.label}
                </span>
              </div>

              {/* Connector line */}
              {index < visibleSteps.length - 1 ? (
                <div
                  className={`h-px w-4 sm:w-6 ${
                    isComplete
                      ? "bg-emerald-500"
                      : "bg-emerald-700/40"
                  }`}
                />
              ) : null}
            </div>
          );
        })}
      </div>

      {/* Terminal state badge */}
      {terminal ? (
        <span
          className={`inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${
            status === "rejected"
              ? "bg-rose-500/15 text-rose-200 ring-1 ring-rose-400/50"
              : "bg-zinc-500/15 text-zinc-200 ring-1 ring-zinc-400/40"
          }`}
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${
              status === "rejected" ? "bg-rose-400" : "bg-zinc-400"
            }`}
          />
          {status === "rejected" ? "Rejected" : "Withdrawn"}
        </span>
      ) : null}
    </div>
  );
}
