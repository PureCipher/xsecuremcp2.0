"use client";

import { useState } from "react";

type PublishManifest = Record<string, unknown>;
type PublishMetadata = Record<string, unknown>;

type PublishRequestBody = {
  display_name: string;
  categories: string[];
  manifest: PublishManifest;
  metadata: PublishMetadata;
};

type PreflightFinding = {
  severity?: string;
  message?: string;
  summary?: string;
};

type PublisherPreflightResponse = {
  error?: string;
  ready_for_publish?: boolean;
  summary?: string;
  effective_certification_level?: string;
  minimum_required_level?: string;
  report?: {
    findings?: PreflightFinding[];
  };
};

export function PublisherForm() {
  const [displayName, setDisplayName] = useState("");
  const [categories, setCategories] = useState("network,utility");
  const [manifestText, setManifestText] = useState("{\n  \"tool_name\": \"\",\n  \"version\": \"1.0.0\",\n  \"author\": \"\",\n  \"description\": \"\",\n  \"permissions\": [],\n  \"data_flows\": [],\n  \"resource_access\": [],\n  \"tags\": []\n}");
  const [runtimeText, setRuntimeText] = useState("{}");
  const [preflight, setPreflight] = useState<PublisherPreflightResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function parseCommonBody(): PublishRequestBody {
    const body: PublishRequestBody = {
      display_name: "",
      categories: [],
      manifest: {},
      metadata: {},
    };
    body.display_name = displayName.trim();
    body.categories = categories
      .split(",")
      .map((category) => category.trim())
      .filter(Boolean);
    body.manifest = JSON.parse(manifestText) as PublishManifest;
    body.metadata = runtimeText.trim()
      ? (JSON.parse(runtimeText) as PublishMetadata)
      : {};
    return body;
  }

  async function runPreflight() {
    setError(null);
    setSuccess(null);
    setPreflight(null);
    try {
      const body = parseCommonBody();
      const response = await fetch("/api/publish/preflight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json()) as PublisherPreflightResponse;
      if (!response.ok || payload.error) {
        setError(payload.error ?? "Preflight failed.");
      } else {
        setPreflight(payload);
      }
    } catch (err) {
      console.error("Preflight error", err);
      setError("Manifest and runtime metadata must be valid JSON.");
    }
  }

  async function runSubmit() {
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const body = parseCommonBody();
      const response = await fetch("/api/publish/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok || payload.error) {
        setError(payload.error ?? "Publish failed.");
      } else {
        setSuccess("Listing created.");
      }
    } catch (err) {
      console.error("Publish error", err);
      setError("Manifest and runtime metadata must be valid JSON.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="grid gap-6 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1.2fr)]">
      <div className="space-y-4 rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
        <div className="space-y-2">
          <label className="block text-xs font-medium text-emerald-100">
            Display name
            <input
              className="mt-1 w-full rounded-xl border border-emerald-700/70 bg-emerald-950/60 px-3 py-2 text-emerald-50 outline-none ring-0 transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/70"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Weather Lookup"
            />
          </label>
        </div>
        <div className="space-y-2">
          <label className="block text-xs font-medium text-emerald-100">
            Categories (comma-separated)
            <input
              className="mt-1 w-full rounded-xl border border-emerald-700/70 bg-emerald-950/60 px-3 py-2 text-emerald-50 outline-none ring-0 transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/70"
              value={categories}
              onChange={(e) => setCategories(e.target.value)}
              placeholder="network,utility"
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-2 text-[11px] text-emerald-200/90">
          <button
            type="button"
            onClick={runPreflight}
            className="rounded-full bg-emerald-400 px-4 py-2 text-[11px] font-semibold text-emerald-950 shadow-sm transition hover:bg-emerald-300"
          >
            Run preflight
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={runSubmit}
            className="rounded-full border border-emerald-500/80 px-4 py-2 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-500/10 disabled:opacity-60"
          >
            {submitting ? "Publishing…" : "Publish"}
          </button>
        </div>
        {error ? <p className="text-[11px] text-rose-300">{error}</p> : null}
        {success ? <p className="text-[11px] text-emerald-200">{success}</p> : null}
        {preflight ? (
          <div className="mt-2 space-y-2 rounded-2xl bg-emerald-950/70 p-3 text-[11px] ring-1 ring-emerald-700/70">
            <div className="flex items-center justify-between gap-2">
              <p className="font-semibold text-emerald-50">Preflight result</p>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  preflight.ready_for_publish
                    ? "bg-emerald-500/20 text-emerald-200"
                    : "bg-amber-500/20 text-amber-100"
                }`}
              >
                {preflight.ready_for_publish ? "Ready to publish" : "Needs changes"}
              </span>
            </div>
            <p className="text-emerald-100/90">{preflight.summary}</p>
            <div className="mt-1 grid gap-2 text-emerald-200/90 sm:grid-cols-2">
              <div>
                <span className="font-semibold text-emerald-50">Effective level:</span>{" "}
                {preflight.effective_certification_level}
              </div>
              <div>
                <span className="font-semibold text-emerald-50">Registry minimum:</span>{" "}
                {preflight.minimum_required_level}
              </div>
            </div>
            {Array.isArray(preflight.report?.findings) && preflight.report.findings.length > 0 ? (
                  <div className="mt-2 space-y-1">
                <p className="font-semibold text-emerald-50">Guardrail findings</p>
                <ul className="space-y-1 text-emerald-200/90">
                  {preflight.report.findings.slice(0, 4).map((finding, index) => (
                    <li key={index} className="text-[10px] leading-snug">
                      <span className="font-semibold">
                        {finding.severity?.toUpperCase?.() ?? "INFO"}:
                      </span>{" "}
                      {finding.message ?? finding.summary ?? "See certification report."}
                    </li>
                  ))}
                  {preflight.report.findings.length > 4 ? (
                    <li className="text-[10px] text-emerald-300/90">
                      +{preflight.report.findings.length - 4} more finding
                      {preflight.report.findings.length - 4 === 1 ? "" : "s"} in the full report.
                    </li>
                  ) : null}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="space-y-4">
        <div className="space-y-2 rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
          <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
            Manifest JSON
          </h2>
          <textarea
            value={manifestText}
            onChange={(e) => setManifestText(e.target.value)}
            className="h-48 w-full rounded-xl border border-emerald-700/70 bg-emerald-950/60 p-3 text-[11px] font-mono text-emerald-50 outline-none ring-0 transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/70"
          />
        </div>
        <div className="space-y-2 rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
          <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
            Runtime metadata JSON
          </h2>
          <textarea
            value={runtimeText}
            onChange={(e) => setRuntimeText(e.target.value)}
            className="h-36 w-full rounded-xl border border-emerald-700/70 bg-emerald-950/60 p-3 text-[11px] font-mono text-emerald-50 outline-none ring-0 transition focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/70"
          />
        </div>
      </div>
    </section>
  );
}
