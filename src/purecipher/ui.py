"""Server-rendered UI for the PureCipher registry."""

from __future__ import annotations

import html
import json
from typing import Any
from urllib.parse import quote, urlencode

SAMPLE_MANIFEST_JSON = json.dumps(
    {
        "tool_name": "weather-lookup",
        "version": "1.0.0",
        "author": "acme",
        "description": "Fetch current weather for a city.",
        "permissions": ["network_access"],
        "data_flows": [
            {
                "source": "input.city",
                "destination": "output.forecast",
                "classification": "public",
                "description": "City name is sent to the weather provider.",
            }
        ],
        "resource_access": [
            {
                "resource_pattern": "https://api.weather.example/*",
                "access_type": "read",
                "description": "Call weather provider endpoint.",
                "classification": "public",
            }
        ],
        "tags": ["weather", "api"],
    },
    indent=2,
)

SAMPLE_RUNTIME_METADATA_JSON = json.dumps(
    {
        "endpoint": "https://mcp.acme.example/weather",
        "transport": "streamable-http",
        "command": "uvx",
        "args": ["weather-lookup"],
        "docker_image": "ghcr.io/acme/weather-lookup:1.0.0",
        "env": {"WEATHER_API_KEY": "${WEATHER_API_KEY}"},
    },
    indent=2,
)

PUBLISHER_PRESETS = {
    "remote-http": {
        "label": "Remote HTTP",
        "display_name": "Weather Lookup",
        "categories": "network,utility",
        "tags": "weather,api",
        "requested_level": "basic",
        "source_url": "https://github.com/acme/weather-lookup",
        "homepage_url": "https://acme.example/weather",
        "tool_license": "MIT",
        "manifest_text": SAMPLE_MANIFEST_JSON,
        "runtime_metadata_text": SAMPLE_RUNTIME_METADATA_JSON,
    },
    "local-stdio": {
        "label": "Local stdio",
        "display_name": "Filesystem Scout",
        "categories": "file_system,utility",
        "tags": "filesystem,local",
        "requested_level": "standard",
        "source_url": "https://github.com/acme/filesystem-scout",
        "homepage_url": "",
        "tool_license": "Apache-2.0",
        "manifest_text": json.dumps(
            {
                "tool_name": "filesystem-scout",
                "version": "1.2.0",
                "author": "acme",
                "description": "Inspect approved local paths and summarize file state.",
                "permissions": ["read_resource"],
                "data_flows": [
                    {
                        "source": "resource.local_path",
                        "destination": "output.summary",
                        "classification": "internal",
                        "description": "Local file metadata is summarized for the caller.",
                    }
                ],
                "resource_access": [
                    {
                        "resource_pattern": "file:///workspace/*",
                        "access_type": "read",
                        "description": "Read approved workspace paths only.",
                        "classification": "internal",
                    }
                ],
                "tags": ["filesystem", "local"],
            },
            indent=2,
        ),
        "runtime_metadata_text": json.dumps(
            {
                "command": "uvx",
                "args": ["filesystem-scout"],
                "env": {"ALLOWED_ROOT": "${ALLOWED_ROOT}"},
            },
            indent=2,
        ),
    },
    "dockerized": {
        "label": "Dockerized",
        "display_name": "Ledger Scan",
        "categories": "data_access,monitoring",
        "tags": "ledger,compliance",
        "requested_level": "standard",
        "source_url": "https://github.com/acme/ledger-scan",
        "homepage_url": "https://acme.example/ledger-scan",
        "tool_license": "MIT",
        "manifest_text": json.dumps(
            {
                "tool_name": "ledger-scan",
                "version": "0.9.0",
                "author": "acme",
                "description": "Inspect ledger state and expose compliance checks over MCP.",
                "permissions": ["network_access", "read_resource"],
                "data_flows": [
                    {
                        "source": "input.account_id",
                        "destination": "output.report",
                        "classification": "confidential",
                        "description": "Account identifiers are checked against compliance rules.",
                    }
                ],
                "resource_access": [
                    {
                        "resource_pattern": "https://ledger.acme.example/*",
                        "access_type": "read",
                        "description": "Read-only access to the ledger API.",
                        "classification": "confidential",
                    }
                ],
                "tags": ["ledger", "compliance"],
            },
            indent=2,
        ),
        "runtime_metadata_text": json.dumps(
            {
                "endpoint": "https://mcp.acme.example/ledger-scan",
                "transport": "streamable-http",
                "docker_image": "ghcr.io/acme/ledger-scan:0.9.0",
                "env": {"LEDGER_TOKEN": "${LEDGER_TOKEN}"},
            },
            indent=2,
        ),
    },
}

BASE_STYLES = """
:root {
  --bg: #f5f1e8;
  --panel: #fffdf8;
  --ink: #17212b;
  --muted: #5f6b76;
  --line: #d8d2c8;
  --accent: #165f55;
  --accent-soft: #edf5f3;
  --accent-strong: #0f4e46;
  --danger: #8f3f31;
  --danger-soft: #fbeae6;
  --success: #0f6e48;
  --success-soft: #ebf6ef;
}

html {
  scroll-behavior: smooth;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(22, 95, 85, 0.08), transparent 24%),
    linear-gradient(180deg, #f8f5ee 0%, var(--bg) 100%);
  color: var(--ink);
  font-family: "Avenir Next", "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  overflow-x: hidden;
}

a {
  color: var(--accent);
  text-decoration-thickness: 1.5px;
  text-underline-offset: 0.18em;
}

a:hover {
  color: var(--accent-strong);
}

::selection {
  background: rgba(22, 95, 85, 0.16);
}

code,
pre {
  font-family: "SFMono-Regular", Menlo, Consolas, monospace;
}

.shell {
  max-width: 1240px;
  margin: 0 auto;
  padding: 28px 20px 40px;
}

.topbar,
.auth-panel {
  background: rgba(255, 253, 248, 0.9);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 10px 30px rgba(23, 33, 43, 0.06);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px;
  margin-bottom: 18px;
  position: sticky;
  top: 12px;
  z-index: 20;
  backdrop-filter: blur(14px);
}

.brand-lockup,
.session-strip {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(145deg, #165f55, #1d7e72);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.brand-name {
  font-family: "Iowan Old Style", Georgia, serif;
  font-size: 1.05rem;
  font-weight: 700;
}

.brand-note {
  color: var(--muted);
  font-size: 0.84rem;
}

.brand-name,
.brand-note,
.session-meta strong,
.session-meta span,
.metric .value,
.detail-box .value,
.mini-card .value,
.catalog-meta,
.catalog-description,
.catalog-tags,
.detail-note,
.definition-grid dd,
.notice,
.pill,
.listing-chip,
.action-link,
.copy-button,
button {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.nav-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  padding: 9px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  color: var(--muted);
  text-decoration: none;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
}

.nav-link:hover,
.nav-link.is-current {
  border-color: var(--line);
  background: #fff;
  color: var(--ink);
}

.session-strip {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.session-meta {
  text-align: right;
}

.session-meta strong {
  display: block;
}

.role-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero,
.panel,
.catalog-item,
.notice,
.metric,
.detail-box,
.recipe,
.listing-chip {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 10px 30px rgba(23, 33, 43, 0.06);
}

.hero,
.panel {
  padding: 24px;
}

.hero {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at top right, rgba(22, 95, 85, 0.11), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(255, 253, 248, 0.96));
}

.hero::after {
  content: "";
  position: absolute;
  inset: auto -12% -42% auto;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(22, 95, 85, 0.08), transparent 64%);
  pointer-events: none;
}

.eyebrow {
  margin-bottom: 10px;
  color: var(--accent);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

h1,
h2,
h3 {
  margin: 0;
  font-family: "Iowan Old Style", Georgia, serif;
}

h1 {
  font-size: clamp(2rem, 4vw, 3.3rem);
  line-height: 0.98;
}

h2 {
  font-size: clamp(1.5rem, 2.4vw, 2rem);
}

h3 {
  font-size: 1.05rem;
}

.subtle,
.catalog-meta,
.catalog-tags,
.hero-copy,
.detail-note,
.footer-links {
  color: var(--muted);
}

.hero-copy {
  max-width: 760px;
  margin: 12px 0 0;
  line-height: 1.6;
}

.hero-actions,
.footer-links,
.action-row,
.chip-row,
.jump-links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-actions,
.footer-links,
.jump-links {
  margin-top: 18px;
}

.action-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  text-decoration: none;
  text-align: center;
  white-space: normal;
  transition:
    transform 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease,
    background 160ms ease;
}

.button-secondary {
  background: #fff;
  color: var(--ink);
  border: 1px solid var(--line);
}

.button-secondary:hover {
  background: rgba(255, 255, 255, 0.94);
}

.copy-button {
  width: auto;
  padding: 9px 12px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.92);
  color: var(--ink);
  white-space: nowrap;
}

.copy-button.is-copied {
  background: var(--success-soft);
  color: var(--success);
  border-color: rgba(15, 110, 72, 0.28);
}

.action-link:hover,
button:hover {
  transform: translateY(-1px);
  border-color: rgba(22, 95, 85, 0.34);
  box-shadow: 0 10px 24px rgba(23, 33, 43, 0.12);
}

.jump-link {
  background: rgba(255, 255, 255, 0.78);
}

.micro-note {
  color: var(--muted);
  font-size: 0.84rem;
  line-height: 1.5;
}

.metrics,
.section-grid,
.detail-grid,
.install-grid,
.submit-grid,
.hero-cluster,
.preset-grid,
.launchpad-grid,
.publish-grid {
  display: grid;
  gap: 12px;
}

.metrics {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin-top: 18px;
}

.topbar > *,
.hero-cluster > *,
.layout > *,
.metrics > *,
.section-grid > *,
.detail-grid > *,
.install-grid > *,
.submit-grid > *,
.publish-grid > *,
.launchpad-grid > *,
.preset-grid > *,
.catalog > *,
.publisher-directory > *,
.publisher-highlight-grid > *,
.publisher-grid > *,
.queue-section-grid > *,
.dashboard-stack > * {
  min-width: 0;
}

.hero-cluster {
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.76fr);
  align-items: start;
  gap: 18px;
}

.metric,
.detail-box {
  padding: 14px;
}

.metric .label,
.detail-box .label {
  color: var(--muted);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.metric .value,
.detail-box .value {
  margin-top: 8px;
  font-size: clamp(1rem, 1.9vw, 1.2rem);
  font-weight: 700;
  line-height: 1.25;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 18px;
  margin-top: 18px;
}

.layout > .panel:last-child {
  position: sticky;
  top: 98px;
  align-self: start;
}

.page-stack {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

/* Login-specific tweaks */
.shell.is-login {
  max-width: 1000px;
}

.shell.is-login .hero {
  margin-bottom: 16px;
}

.shell.is-login .panel {
  padding: 26px 24px 28px;
}

.login-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  gap: 28px;
  align-items: center;
}

.login-copy h2 {
  margin: 0;
  font-family: "Iowan Old Style", Georgia, serif;
  font-size: 1.4rem;
}

.login-copy p {
  margin-top: 10px;
  color: var(--muted);
  font-size: 0.95rem;
}

.login-points {
  margin: 16px 0 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.4;
}

.login-form-wrapper {
  display: flex;
  justify-content: center;
}

.login-form-wrapper .auth-panel {
  width: 100%;
  max-width: 360px;
}

@media (max-width: 768px) {
  .shell.is-login {
    max-width: 100%;
    padding-inline: 16px;
  }

  .login-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 18px;
  }

  .login-form-wrapper {
    justify-content: stretch;
  }
}

.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

form.search-form,
.submit-grid {
  display: grid;
  gap: 10px;
}

form.search-form {
  grid-template-columns: minmax(0, 1fr) 220px auto;
  margin-bottom: 14px;
}

.submit-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.publish-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.field-stack {
  display: grid;
  gap: 6px;
}

.field-label {
  color: var(--muted);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.results-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 16px;
}

.results-summary {
  color: var(--muted);
}

.auth-panel {
  padding: 18px;
}

.auth-grid,
.publisher-directory,
.role-grid {
  display: grid;
  gap: 12px;
}

.auth-grid,
.role-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.publisher-directory {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

input,
select,
textarea,
button {
  width: 100%;
  font: inherit;
}

input,
select,
textarea {
  padding: 11px 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  color: var(--ink);
}

input:focus,
select:focus,
textarea:focus {
  outline: none;
  border-color: rgba(22, 95, 85, 0.55);
  box-shadow: 0 0 0 4px rgba(22, 95, 85, 0.12);
}

textarea {
  min-height: 240px;
  resize: vertical;
  font-size: 0.88rem;
  line-height: 1.5;
}

button {
  padding: 11px 14px;
  border: 0;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    background 160ms ease;
}

.catalog {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.catalog-item {
  display: block;
  padding: 16px;
  color: inherit;
  text-decoration: none;
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.catalog-item:hover,
.moderation-card:hover,
.publisher-card:hover,
.recipe:hover {
  transform: translateY(-2px);
  border-color: rgba(22, 95, 85, 0.38);
  box-shadow: 0 14px 32px rgba(23, 33, 43, 0.1);
}

.catalog-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.catalog-actions {
  margin-top: 12px;
}

.catalog-description {
  margin: 10px 0;
  line-height: 1.55;
}

.pill,
.listing-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
}

.pill {
  background: var(--accent-soft);
  color: var(--accent);
}

.listing-chip {
  background: #fff;
  box-shadow: none;
}

.detail-stack {
  display: grid;
  gap: 10px;
}

.detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.pathway-grid,
.status-grid,
.help-grid {
  display: grid;
  gap: 12px;
}

.pathway-grid,
.status-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.help-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.issue-list,
.bullet-list {
  margin: 10px 0 0 18px;
  padding: 0;
}

.notice {
  padding: 12px 14px;
}

.notice-success {
  background: var(--success-soft);
  color: var(--success);
  border-color: rgba(15, 110, 72, 0.2);
}

.notice-error {
  background: var(--danger-soft);
  color: var(--danger);
  border-color: rgba(143, 63, 49, 0.2);
}

.empty {
  padding: 24px;
  border: 1px dashed var(--line);
  border-radius: 16px;
  color: var(--muted);
  text-align: center;
}

.section-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.section-card {
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
}

.section-card.is-accent {
  background:
    linear-gradient(180deg, rgba(237, 245, 243, 0.92), rgba(255, 255, 255, 0.92));
  border-color: rgba(22, 95, 85, 0.18);
}

.section-card p,
.detail-note {
  line-height: 1.6;
}

.field-hint {
  margin-top: 8px;
  color: var(--muted);
  font-size: 0.84rem;
  line-height: 1.5;
}

.checklist {
  display: grid;
  gap: 10px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.checklist li {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
}

.section-kicker {
  margin-bottom: 8px;
  color: var(--accent);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.stacked-panels {
  display: grid;
  gap: 14px;
}

.hero-side-stack {
  display: grid;
  gap: 12px;
}

.quick-link-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.decision-grid,
.story-grid {
  display: grid;
  gap: 12px;
}

.decision-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.story-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.decision-card,
.story-card {
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 10px 24px rgba(23, 33, 43, 0.05);
}

.decision-card.is-primary {
  background:
    linear-gradient(180deg, rgba(237, 245, 243, 0.94), rgba(255, 255, 255, 0.94));
  border-color: rgba(22, 95, 85, 0.2);
}

.decision-card p,
.story-card p {
  margin: 10px 0 0;
  color: var(--muted);
  line-height: 1.6;
}

.story-card strong,
.decision-card strong {
  display: inline-block;
  font-size: 1rem;
}

.simple-list {
  display: grid;
  gap: 10px;
  margin: 12px 0 0;
}

.simple-item {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--muted);
  line-height: 1.55;
}

.inline-code {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid var(--line);
  color: var(--ink);
  font-size: 0.84rem;
}

.definition-grid {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 8px 12px;
  margin-top: 12px;
}

.definition-grid dt {
  color: var(--muted);
  font-weight: 700;
}

.definition-grid dd {
  margin: 0;
}

.code-block {
  overflow-x: auto;
  margin: 12px 0 0;
  padding: 14px;
  border-radius: 14px;
  background: #0f1720;
  color: #f8fafc;
  font-size: 0.84rem;
  line-height: 1.5;
}

.code-block::-webkit-scrollbar {
  height: 10px;
}

.code-block::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.18);
  border-radius: 999px;
}

.copy-source {
  display: none;
}

.recipe {
  padding: 16px;
}

.recipe-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.recipe-actions,
.recipe-overview {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.recipe-overview {
  margin-bottom: 14px;
}

.recipe-summary {
  color: var(--muted);
}

.install-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.publisher-grid,
.queue-section-grid {
  display: grid;
  gap: 12px;
}

.dashboard-stack,
.publisher-highlight-grid,
.pulse-grid {
  display: grid;
  gap: 12px;
}

.pulse-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mini-card {
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
}

.mini-card .label {
  color: var(--muted);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.mini-card .value {
  margin-top: 8px;
  font-size: clamp(0.98rem, 1.7vw, 1.08rem);
  font-weight: 700;
  line-height: 1.25;
}

.publisher-highlight-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.preset-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.preset-card {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
}

.launchpad-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.publisher-card {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.76);
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.compact-list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.compact-item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
}

.moderation-card {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.moderation-form {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.moderation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.moderation-actions button {
  width: auto;
  min-width: 120px;
}

.manifest-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 920px) {
  .topbar {
    flex-direction: column;
    align-items: flex-start;
    position: static;
  }

  .session-strip,
  .session-meta {
    justify-content: flex-start;
    text-align: left;
  }

  .hero-cluster,
  .layout,
  .section-grid,
  .story-grid,
  .help-grid,
  .manifest-columns,
  form.search-form,
  .submit-grid,
  .publish-grid,
  .launchpad-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .layout > .panel:last-child {
    position: static;
  }

  .catalog {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .shell {
    padding: 18px 14px 28px;
  }

  .hero,
  .panel {
    padding: 18px;
  }

  .nav-links {
    width: 100%;
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: 2px;
    scrollbar-width: none;
  }

  .nav-links::-webkit-scrollbar {
    display: none;
  }

  .panel-head,
  .catalog-row,
  .compact-item,
  .recipe-head,
  .results-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .publisher-directory,
  .publisher-highlight-grid,
  .preset-grid,
  .install-grid {
    grid-template-columns: 1fr;
  }

  .pulse-grid {
    grid-template-columns: 1fr;
  }

  .moderation-actions button,
  .action-link,
  .copy-button,
  .button-secondary {
    width: 100%;
    justify-content: center;
  }

  .hero-actions,
  .footer-links,
  .action-row,
  .jump-links {
    display: grid;
    grid-template-columns: 1fr;
  }

  textarea {
    min-height: 200px;
  }
}

@media (max-width: 480px) {
  h1 {
    font-size: 1.8rem;
  }

  h2 {
    font-size: 1.35rem;
  }

  .metrics {
    grid-template-columns: 1fr;
  }

  .definition-grid {
    grid-template-columns: 1fr;
  }
}
"""

LISTING_INTERACTIONS_SCRIPT = f"""
<script>
const REGISTRY_PUBLISH_PRESETS = {json.dumps(PUBLISHER_PRESETS)};

function setRegistryField(id, value) {{
  const field = document.getElementById(id);
  if (field) {{
    field.value = value || "";
  }}
}}

function applyRegistryPreset(name) {{
  const preset = REGISTRY_PUBLISH_PRESETS[name];
  if (!preset) {{
    return;
  }}
  setRegistryField("publish-display-name", preset.display_name);
  setRegistryField("publish-categories", preset.categories);
  setRegistryField("publish-tags", preset.tags);
  setRegistryField("publish-requested-level", preset.requested_level);
  setRegistryField("publish-source-url", preset.source_url);
  setRegistryField("publish-homepage-url", preset.homepage_url);
  setRegistryField("publish-license", preset.tool_license);
  setRegistryField("publish-runtime-metadata", preset.runtime_metadata_text);
  setRegistryField("publish-manifest", preset.manifest_text);
}}

async function copyRegistryBlock(button) {{
  const targetId = button.getAttribute("data-copy-target");
  const target = document.getElementById(targetId);
  if (!target) {{
    return;
  }}

  const originalLabel = button.getAttribute("data-original-label") || button.textContent;
  const text = target.textContent || "";

  async function fallbackCopy(value) {{
    const helper = document.createElement("textarea");
    helper.value = value;
    helper.setAttribute("readonly", "");
    helper.style.position = "absolute";
    helper.style.left = "-9999px";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    document.body.removeChild(helper);
  }}

  try {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      await navigator.clipboard.writeText(text);
    }} else {{
      await fallbackCopy(text);
    }}
    button.textContent = "Copied";
    button.classList.add("is-copied");
  }} catch (error) {{
    button.textContent = "Select manually";
    button.classList.remove("is-copied");
  }}

  window.clearTimeout(button._copyTimer);
  button._copyTimer = window.setTimeout(() => {{
    button.textContent = originalLabel;
    button.classList.remove("is-copied");
  }}, 1800);
}}
</script>
"""


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{round(value * 100)}%"
    return "n/a"


def _slug(value: str) -> str:
    return quote(value, safe="")


def _catalog_href(
    *,
    registry_prefix: str,
    query: str,
    min_certification: str,
) -> str:
    params = {}
    if query:
        params["q"] = query
    if min_certification:
        params["min_certification"] = min_certification
    if not params:
        return registry_prefix
    return f"{registry_prefix}?{urlencode(params)}"


def _tool_href(
    *,
    registry_prefix: str,
    tool_name: str,
    query: str,
    min_certification: str,
) -> str:
    params = {}
    if query:
        params["q"] = query
    if min_certification:
        params["min_certification"] = min_certification
    suffix = f"?{urlencode(params)}" if params else ""
    return f"{registry_prefix}/listings/{_slug(tool_name)}{suffix}"


def _publisher_href(*, registry_prefix: str, publisher_id: str) -> str:
    return f"{registry_prefix}/publishers/{_slug(publisher_id)}"


def _publisher_index_href(*, registry_prefix: str) -> str:
    return f"{registry_prefix}/publishers?view=html"


def _publish_href(*, registry_prefix: str) -> str:
    return f"{registry_prefix}/publish"


def _login_href(*, registry_prefix: str, next_path: str = "") -> str:
    if not next_path:
        return f"{registry_prefix}/login"
    return f"{registry_prefix}/login?{urlencode({'next': next_path})}"


def _logout_href(*, registry_prefix: str, next_path: str = "") -> str:
    if not next_path:
        return f"{registry_prefix}/logout"
    return f"{registry_prefix}/logout?{urlencode({'next': next_path})}"


def _can_review_registry(
    *,
    auth_enabled: bool,
    session: dict[str, Any] | None,
) -> bool:
    return not auth_enabled or bool(session and session.get("can_review"))


def _pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _render_topbar(
    *,
    registry_prefix: str,
    auth_enabled: bool,
    session: dict[str, Any] | None,
    current_page: str,
    current_path: str,
) -> str:
    if current_page == "login":
        nav_html = ""
    else:
        nav_items = [
            ("catalog", "Browse", registry_prefix),
            ("publish", "Share", _publish_href(registry_prefix=registry_prefix)),
            (
                "publishers",
                "Publishers",
                _publisher_index_href(registry_prefix=registry_prefix),
            ),
        ]
        if _can_review_registry(auth_enabled=auth_enabled, session=session):
            nav_items.append(("review", "Approvals", f"{registry_prefix}/review"))
        nav_html = "".join(
            f'<a class="nav-link{" is-current" if page == current_page else ""}" href="{_escape(href)}">{_escape(label)}</a>'
            for page, label, href in nav_items
        )

    if current_page == "login":
        session_html = ""
    else:
        if not auth_enabled:
            session_html = (
                '<div class="session-strip">'
                '<span class="role-pill">Open access</span>'
                '<div class="session-meta"><strong>Open access</strong>'
                '<span class="brand-note">Anyone can browse and preview tools.</span></div>'
                "</div>"
            )
        elif session is None:
            session_html = (
                '<div class="session-strip">'
                '<span class="role-pill">Sign-in available</span>'
                '<a class="action-link" href="'
                f'{_escape(_login_href(registry_prefix=registry_prefix, next_path=current_path))}">Sign in</a>'
                "</div>"
            )
        else:
            session_html = (
                '<div class="session-strip">'
                f'<span class="role-pill">{_escape(session.get("role", "viewer"))}</span>'
                '<div class="session-meta">'
                f"<strong>{_escape(session.get('display_name') or session.get('username') or 'Authenticated user')}</strong>"
                f'<span class="brand-note">{_escape(session.get("username") or "")}</span>'
                "</div>"
                f'<a class="action-link" href="{_escape(_logout_href(registry_prefix=registry_prefix, next_path=current_path))}">Sign out</a>'
                "</div>"
            )

    return f"""
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark">PC</div>
        <div>
          <div class="brand-name">PureCipher Secured MCP Registry</div>
          <div class="brand-note">Find trusted tools, learn how to use them, and share your own.</div>
        </div>
      </div>
      <nav class="nav-links">{nav_html}</nav>
      {session_html}
    </header>
    """


def _render_copy_button(*, target_id: str, label: str = "Copy block") -> str:
    return (
        '<button class="copy-button" type="button" '
        f'data-copy-target="{_escape(target_id)}" '
        f'data-original-label="{_escape(label)}" '
        'onclick="copyRegistryBlock(this)">'
        f"{_escape(label)}"
        "</button>"
    )


def _render_chip_row(values: list[str]) -> str:
    if not values:
        return '<div class="detail-note">Nothing added yet.</div>'
    return "".join(
        f'<span class="listing-chip">{_escape(value)}</span>' for value in values
    )


def _render_bullet_list(values: list[str]) -> str:
    if not values:
        return '<div class="detail-note">Nothing added yet.</div>'
    items = "".join(f"<li>{_escape(value)}</li>" for value in values)
    return f'<ul class="bullet-list">{items}</ul>'


def _render_verification_issues(verification: dict[str, Any]) -> str:
    issues = verification.get("issues") or []
    if not issues:
        return "<li>No issues were found.</li>"
    return "".join(f"<li>{_escape(issue)}</li>" for issue in issues)


def _render_data_flows(manifest: dict[str, Any]) -> str:
    flows = manifest.get("data_flows") or []
    if not flows:
        return '<div class="detail-note">No data sharing details were added.</div>'
    items = []
    for flow in flows:
        items.append(
            '<div class="detail-box">'
            f'<div class="label">{_escape(flow.get("classification", "internal"))}</div>'
            f'<div class="value">{_escape(flow.get("source", "unknown"))} -> {_escape(flow.get("destination", "unknown"))}</div>'
            f'<div class="detail-note">{_escape(flow.get("description", "No description provided."))}</div>'
            "</div>"
        )
    return "".join(items)


def _render_resource_access(manifest: dict[str, Any]) -> str:
    access_items = manifest.get("resource_access") or []
    if not access_items:
        return '<div class="detail-note">No connected data sources were listed.</div>'
    items = []
    for access in access_items:
        items.append(
            '<div class="detail-box">'
            f'<div class="label">{_escape(access.get("access_type", "read"))}</div>'
            f'<div class="value">{_escape(access.get("resource_pattern", "unknown"))}</div>'
            f'<div class="detail-note">{_escape(access.get("description", "No description provided."))}</div>'
            "</div>"
        )
    return "".join(items)


def _render_catalog(
    *,
    registry_prefix: str,
    catalog: dict[str, Any],
    query: str,
    min_certification: str,
) -> str:
    tools = list(catalog.get("tools", []))
    if not tools:
        return '<div class="empty">Nothing matches those filters yet.</div>'

    items: list[str] = []
    for tool in tools:
        href = _tool_href(
            registry_prefix=registry_prefix,
            tool_name=str(tool.get("tool_name", "")),
            query=query,
            min_certification=min_certification,
        )
        publisher_id = str(tool.get("publisher_id") or "")
        author = _escape(tool.get("author") or "unknown author")
        author_html = (
            f'<a href="{_escape(_publisher_href(registry_prefix=registry_prefix, publisher_id=publisher_id))}">{author}</a>'
            if publisher_id
            else author
        )
        tags = ", ".join(sorted(tool.get("tags", []))) or "no tags"
        categories = ", ".join(sorted(tool.get("categories", []))) or "uncategorized"
        items.append(
            f"""
            <a class="catalog-item" href="{_escape(href)}">
              <div class="catalog-row">
                <strong>{_escape(tool.get("display_name") or tool.get("tool_name"))}</strong>
                <span class="pill">{_escape(tool.get("certification_level") or "uncertified")}</span>
              </div>
              <div class="catalog-meta">
                {author_html} ·
                v{_escape(tool.get("version") or "0.0.0")} ·
                confidence {_percent((tool.get("trust_score") or {}).get("overall"))}
              </div>
              <p class="catalog-description">{_escape(tool.get("description") or "No description provided.")}</p>
              <div class="catalog-tags">Topics: {_escape(categories)}</div>
              <div class="catalog-tags">Keywords: {_escape(tags)}</div>
              <div class="catalog-actions">
                <span class="action-link">View tool</span>
              </div>
            </a>
            """
        )
    return "\n".join(items)


def _render_detail_preview(
    *,
    detail: dict[str, Any] | None,
    registry_prefix: str,
    query: str,
    min_certification: str,
) -> str:
    if not detail:
        return (
            '<div class="empty">Pick a tool to see its details and setup steps.</div>'
        )

    trust = detail.get("trust_score") or {}
    verification = detail.get("verification") or {}
    tool_name = str(detail.get("tool_name") or "")
    listing_href = _tool_href(
        registry_prefix=registry_prefix,
        tool_name=tool_name,
        query=query,
        min_certification=min_certification,
    )
    install_href = f"{registry_prefix}/install/{_slug(tool_name)}"
    return f"""
      <div class="detail-stack">
      <div class="detail-box">
        <div class="label">Selected Tool</div>
        <div class="value">{_escape(detail.get("display_name") or tool_name)}</div>
        <div class="detail-note">{_escape(detail.get("description") or "No description provided.")}</div>
      </div>
      <div class="detail-grid">
        <div class="detail-box">
          <div class="label">Safety Level</div>
          <div class="value">{_escape(detail.get("certification_level") or "uncertified")}</div>
        </div>
        <div class="detail-box">
          <div class="label">Confidence</div>
          <div class="value">{_percent(trust.get("overall"))}</div>
        </div>
        <div class="detail-box">
          <div class="label">Checks</div>
          <div class="value">{"looks good" if verification.get("valid") else "needs attention"}</div>
        </div>
        <div class="detail-box">
          <div class="label">Uses</div>
          <div class="value">{_escape(detail.get("active_installs") or 0)}</div>
        </div>
      </div>
      <div class="action-row">
        <a class="action-link" href="{_escape(listing_href)}">Open tool page</a>
        <a class="action-link" href="{_escape(install_href)}">Setup data</a>
      </div>
    </div>
    """


def _render_submission_notice(
    *,
    submission_title: str | None,
    submission_body: str | None,
    submission_is_error: bool,
) -> str:
    if not submission_title:
        return '<div class="notice">Open the share flow to add a new tool.</div>'

    tone = "notice-error" if submission_is_error else "notice-success"
    body = f"<div>{_escape(submission_body)}</div>" if submission_body else ""
    return f'<div class="notice {tone}"><strong>{_escape(submission_title)}</strong>{body}</div>'


def _render_optional_notice(
    *,
    notice_title: str | None,
    notice_body: str | None,
    notice_is_error: bool,
) -> str:
    if not notice_title:
        return ""
    tone = "notice-error" if notice_is_error else "notice-success"
    body = f"<div>{_escape(notice_body)}</div>" if notice_body else ""
    return f'<div class="notice {tone}"><strong>{_escape(notice_title)}</strong>{body}</div>'


def _render_dashboard_snapshot(
    *,
    registry_prefix: str,
    health: dict[str, Any],
    queue: dict[str, Any],
    detail: dict[str, Any] | None,
    query: str,
    min_certification: str,
    can_review: bool,
) -> str:
    counts = queue.get("counts") or {}
    pending_items = list((queue.get("sections") or {}).get("pending_review") or [])[:3]
    suspended_items = list((queue.get("sections") or {}).get("suspended") or [])[:3]

    def _render_compact_items(items: list[dict[str, Any]], empty_label: str) -> str:
        if not items:
            return f'<div class="detail-note">{_escape(empty_label)}</div>'
        return "".join(
            f"""
            <div class="compact-item">
              <a href="{
                _escape(
                    _tool_href(
                        registry_prefix=registry_prefix,
                        tool_name=str(item.get("tool_name", "")),
                        query=query,
                        min_certification=min_certification,
                    )
                )
            }">{_escape(item.get("display_name") or item.get("tool_name"))}</a>
              <span class="pill">{_escape(item.get("status") or "unknown")}</span>
            </div>
            """
            for item in items
        )

    moderation_snapshot = (
        f"""
        <div class="detail-note" style="margin-top: 12px;">Waiting for approval</div>
        <div class="compact-list">
          {_render_compact_items(pending_items, "No pending submissions right now.")}
        </div>
        <div class="detail-note" style="margin-top: 14px;">Paused</div>
        <div class="compact-list">
          {_render_compact_items(suspended_items, "No paused tools right now.")}
        </div>
        <div class="action-row" style="margin-top: 12px;">
          <a class="action-link" href="{_escape(f"{registry_prefix}/review")}">Open approvals</a>
          <a class="action-link" href="{_escape(f"{registry_prefix}/review/submissions")}">Queue data</a>
        </div>
        """
        if can_review
        else f"""
        <div class="detail-note" style="margin-top: 12px;">
          There are {_escape(counts.get("pending_review", health.get("pending_review", 0)))} tools waiting for approval and {_escape(counts.get("suspended", 0))} paused tools right now.
        </div>
        <div class="detail-note" style="margin-top: 10px;">
          Approval details are visible to reviewers and admins.
        </div>
        """
    )

    return f"""
    <div class="dashboard-stack">
      <div class="pulse-grid">
        <div class="mini-card">
          <div class="label">Live</div>
          <div class="value">{
        _escape(counts.get("published", health.get("verified_tools", 0)))
    }</div>
        </div>
        <div class="mini-card">
          <div class="label">Waiting</div>
          <div class="value">{
        _escape(counts.get("pending_review", health.get("pending_review", 0)))
    }</div>
        </div>
        <div class="mini-card">
          <div class="label">Paused</div>
          <div class="value">{_escape(counts.get("suspended", 0))}</div>
        </div>
        <div class="mini-card">
          <div class="label">Review Flow</div>
          <div class="value">{
        _escape("enabled" if queue.get("require_moderation") else "open publish")
    }</div>
        </div>
      </div>
      <div class="section-card">
        <h3>What Is Happening Now</h3>
        <div class="detail-note">A quick look at what is live, waiting for approval, or temporarily paused.</div>
        {moderation_snapshot}
      </div>
      <div class="section-card">
        <h3>Focused Tool</h3>
        <div class="detail-note">Pick a tool from the list and use this panel as a quick bridge into its full page.</div>
        {
        _render_detail_preview(
            detail=detail,
            registry_prefix=registry_prefix,
            query=query,
            min_certification=min_certification,
        )
    }
      </div>
    </div>
    """


def _render_api_endpoint_details(*, registry_prefix: str) -> str:
    return f"""
    <div class="detail-stack" style="margin-top: 12px;">
      <div class="detail-box">
        <div class="label">Share from scripts</div>
        <div class="value"><code>POST {_escape(f"{registry_prefix}/submit")}</code></div>
      </div>
      <div class="detail-box">
        <div class="label">Check from scripts</div>
        <div class="value"><code>POST {_escape(f"{registry_prefix}/preflight")}</code></div>
      </div>
    </div>
    """


def _render_registry_primary_paths(
    *,
    registry_prefix: str,
    auth_enabled: bool,
    session: dict[str, Any] | None,
) -> str:
    if not auth_enabled:
        role_title = "Share a tool whenever you are ready"
        role_body = "This registry is open to explore. When you want to publish, the share flow is already available."
        role_actions = (
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Open share flow</a>'
            f'<a class="action-link" href="{_escape(_publisher_index_href(registry_prefix=registry_prefix))}">See publishers</a>'
        )
    elif session is None:
        role_title = "Browse first, sign in later"
        role_body = "You do not need an account to learn from tool pages. Sign in only if you want to share or review."
        role_actions = (
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=registry_prefix))}">Sign in</a>'
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Preview sharing</a>'
        )
    elif session.get("can_review"):
        role_title = "Review and share from the same place"
        role_body = (
            "This account can help approve submissions and publish tools of its own."
        )
        role_actions = (
            f'<a class="action-link" href="{_escape(f"{registry_prefix}/review")}">Open approvals</a>'
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Share a tool</a>'
        )
    elif session.get("can_submit"):
        role_title = "You are ready to publish"
        role_body = "Use the share flow to turn your tool into a clear page with setup steps and trust details."
        role_actions = (
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Share a tool</a>'
            f'<a class="action-link" href="{_escape(_publisher_index_href(registry_prefix=registry_prefix))}">Learn from publishers</a>'
        )
    else:
        role_title = "This account is best for exploring"
        role_body = "Use it to browse tools and publisher pages. Switch accounts later if you need to publish or review."
        role_actions = (
            f'<a class="action-link" href="{_escape(_publisher_index_href(registry_prefix=registry_prefix))}">Browse publishers</a>'
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Switch account</a>'
        )

    return f"""
    <section class="panel" style="margin-top: 18px;">
      <div class="panel-head">
        <div>
          <h2>What would you like to do?</h2>
          <div class="subtle">Most people start with one of these three paths.</div>
        </div>
      </div>
      <div class="decision-grid">
        <div class="decision-card is-primary">
          <div class="section-kicker">Use a tool</div>
          <strong>Start with the catalog</strong>
          <p>Search, open a tool page, and copy the setup that fits the way you work.</p>
          <div class="quick-link-grid">
            <a class="action-link" href="#catalog">Browse tools</a>
          </div>
        </div>
        <div class="decision-card">
          <div class="section-kicker">Understand the source</div>
          <strong>See who made it</strong>
          <p>Publisher pages make it easy to compare teams, trust signals, and other tools they share.</p>
          <div class="quick-link-grid">
            <a class="action-link" href="{_escape(_publisher_index_href(registry_prefix=registry_prefix))}">Browse publishers</a>
          </div>
        </div>
        <div class="decision-card">
          <div class="section-kicker">Your path</div>
          <strong>{_escape(role_title)}</strong>
          <p>{_escape(role_body)}</p>
          <div class="quick-link-grid">{role_actions}</div>
        </div>
      </div>
    </section>
    """


def _rank_catalog_terms(
    catalog: dict[str, Any],
    *,
    key: str,
    limit: int = 4,
) -> list[str]:
    counts: dict[str, int] = {}
    for tool in list(catalog.get("tools") or []):
        for value in list(tool.get(key) or []):
            label = str(value).strip()
            if not label:
                continue
            counts[label] = counts.get(label, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]


def _render_registry_experience_cards(
    *,
    registry_prefix: str,
    auth_enabled: bool,
    session: dict[str, Any] | None,
    catalog: dict[str, Any],
    min_certification: str,
) -> str:
    topics = _rank_catalog_terms(catalog, key="categories") or _rank_catalog_terms(
        catalog,
        key="tags",
    )
    topic_links = (
        "".join(
            f'<a class="action-link" href="{_escape(_catalog_href(registry_prefix=registry_prefix, query=topic, min_certification=min_certification))}">{_escape(topic)}</a>'
            for topic in topics
        )
        if topics
        else '<div class="detail-note">Browse the catalog to see which topics show up most often.</div>'
    )

    featured_tools = list(catalog.get("tools") or [])[:3]
    featured_links = (
        "".join(
            f'<a class="action-link" href="{_escape(_tool_href(registry_prefix=registry_prefix, tool_name=str(tool.get("tool_name", "")), query="", min_certification=min_certification))}">{_escape(tool.get("display_name") or tool.get("tool_name") or "Open tool")}</a>'
            for tool in featured_tools
        )
        if featured_tools
        else '<div class="detail-note">No live tools match this view yet. Try a broader search or a lower safety filter.</div>'
    )

    if not auth_enabled:
        next_title = "Browse openly, share when ready"
        next_body = "Anyone can explore tool pages and open the share flow here, so you can learn first and publish later."
        next_actions = (
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Open share flow</a>'
            f'<a class="action-link" href="{_escape(_publisher_index_href(registry_prefix=registry_prefix))}">Meet publishers</a>'
        )
    elif session is None:
        next_title = "You can learn before you sign in"
        next_body = "Browsing stays open. Sign in only when you want to share a tool or help review submissions."
        next_actions = (
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=registry_prefix))}">Sign in</a>'
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Preview sharing flow</a>'
        )
    elif session.get("can_review"):
        next_title = "This account can review and share"
        next_body = "Use the approvals queue to manage submissions, or jump into the share flow when you want to publish one of your own tools."
        next_actions = (
            f'<a class="action-link" href="{_escape(f"{registry_prefix}/review")}">Open approvals</a>'
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Share a tool</a>'
        )
    elif session.get("can_submit"):
        next_title = "This account is ready to share"
        next_body = "You can keep browsing, but you also have everything you need to draft, preview, and publish a tool page from here."
        next_actions = (
            f'<a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Share a tool</a>'
            f'<a class="action-link" href="{_escape(_publisher_index_href(registry_prefix=registry_prefix))}">Learn from other publishers</a>'
        )
    else:
        next_title = "Use this account to browse confidently"
        next_body = "This account is best for exploring tools and publisher pages. Switch accounts later if you need to share or review."
        next_actions = (
            f'<a class="action-link" href="{_escape(_publisher_index_href(registry_prefix=registry_prefix))}">Browse publishers</a>'
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Sign in with another role</a>'
        )

    return f"""
    <section class="panel" style="margin-top: 18px;">
      <div class="panel-head">
        <div>
          <h2>Choose your next step</h2>
          <div class="subtle">Start from the kind of help you want: discover, compare, or publish.</div>
        </div>
      </div>
      <div class="pathway-grid">
        <div class="section-card is-accent">
          <div class="section-kicker">Browse faster</div>
          <h3>Popular topics</h3>
          <div class="detail-note" style="margin-top: 10px;">
            Jump straight into common use cases instead of starting with a blank search.
          </div>
          <div class="quick-link-grid">{topic_links}</div>
        </div>
        <div class="section-card">
          <div class="section-kicker">Good starting points</div>
          <h3>Open a live tool page</h3>
          <div class="detail-note" style="margin-top: 10px;">
            These live tool pages are the fastest way to see what a polished listing looks like.
          </div>
          <div class="quick-link-grid">{featured_links}</div>
        </div>
        <div class="section-card">
          <div class="section-kicker">Best next move</div>
          <h3>{_escape(next_title)}</h3>
          <div class="detail-note" style="margin-top: 10px;">{_escape(next_body)}</div>
          <div class="quick-link-grid">{next_actions}</div>
        </div>
      </div>
    </section>
    """


def _render_publish_experience_cards(
    *,
    registry_prefix: str,
    auth_enabled: bool,
    session: dict[str, Any] | None,
    preflight: dict[str, Any] | None,
) -> str:
    if not auth_enabled:
        status_title = "Sharing is open"
        status_body = (
            "You can draft, preview, and share from this page without signing in."
        )
        status_actions = (
            '<a class="action-link" href="#publish-form">Open the share form</a>'
            '<a class="action-link" href="#preflight">See what gets checked</a>'
        )
    elif session is None:
        status_title = "Preview first, sign in when ready"
        status_body = "You can fill in the page and run checks now. Sign in only when it is time to actually share."
        status_actions = (
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Sign in</a>'
            f'<a class="action-link" href="#publish-form">Start with the form</a>'
        )
    elif session.get("can_submit"):
        status_title = "This account can share"
        status_body = "Run a preview, fix anything confusing, then publish from the same page when it feels ready."
        status_actions = (
            '<a class="action-link" href="#preflight">Run checks</a>'
            '<a class="action-link" href="#publish-form">Finish the draft</a>'
        )
    else:
        status_title = "This account can preview but not share"
        status_body = "You can still learn the workflow here, but you will need a publisher, reviewer, or admin account to send a tool live."
        status_actions = (
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Switch account</a>'
            f'<a class="action-link" href="#preflight">See the checks</a>'
        )

    if preflight is None:
        readiness_title = "What a strong listing includes"
        readiness_body = "A plain-language summary, one real setup path, and an honest record of what the tool can access."
    elif preflight.get("ready_for_publish"):
        readiness_title = "This draft is close"
        readiness_body = "The current draft is ready to share. You can still tighten the wording if you want the public page to read better."
    else:
        readiness_title = "Preview before you publish"
        readiness_body = "The current draft still needs attention. Use the check results below to fix the missing pieces before sharing."

    return f"""
    <section class="panel" style="margin-top: 18px;">
      <div class="panel-head">
        <div>
          <h2>Sharing should feel straightforward</h2>
          <div class="subtle">A strong page does three simple things well: it explains the tool, shows how to start, and stays honest about access.</div>
        </div>
      </div>
      <div class="pathway-grid">
        <div class="section-card is-accent">
          <div class="section-kicker">Account status</div>
          <h3>{_escape(status_title)}</h3>
          <div class="detail-note" style="margin-top: 10px;">{_escape(status_body)}</div>
          <div class="quick-link-grid">{status_actions}</div>
        </div>
        <div class="section-card">
          <div class="section-kicker">What people care about</div>
          <h3>Make the page useful</h3>
          <ul class="checklist">
            <li>Tell people what the tool helps with in one clean sentence.</li>
            <li>Include at least one real setup path so the page does not feel theoretical.</li>
            <li>Be honest about permissions, data sharing, and connected sources.</li>
          </ul>
        </div>
        <div class="section-card">
          <div class="section-kicker">Before you share</div>
          <h3>{_escape(readiness_title)}</h3>
          <div class="detail-note" style="margin-top: 10px;">{_escape(readiness_body)}</div>
          <div class="quick-link-grid">
            <a class="action-link" href="#preflight">Open check results</a>
            <a class="action-link" href="#publish-form">Finish the draft</a>
          </div>
        </div>
      </div>
    </section>
    """


def _render_listing_experience_cards(
    *,
    registry_prefix: str,
    detail: dict[str, Any],
    install_recipes: list[dict[str, Any]],
    publisher_href: str,
) -> str:
    primary_recipe = install_recipes[0] if install_recipes else None
    manifest = detail.get("manifest") or {}
    categories = sorted(detail.get("categories") or [])
    permission_count = len(list(manifest.get("permissions") or []))
    resource_count = len(list(manifest.get("resource_access") or []))
    data_flow_count = len(list(manifest.get("data_flows") or []))
    tool_name = str(detail.get("tool_name") or "")

    if primary_recipe is None:
        start_title = "Setup details are still on the way"
        start_body = "The page is live, but the publisher has not added a ready-to-copy setup path yet."
        start_actions = f'<a class="action-link" href="{_escape(f"{registry_prefix}/install/{_slug(tool_name)}")}">Open setup data</a>'
    else:
        recipe_id = _slug(str(primary_recipe.get("recipe_id") or "primary"))
        start_title = str(primary_recipe.get("title") or "Quickest setup path")
        start_body = str(
            primary_recipe.get("description")
            or "Most people start here when they want to use this tool quickly."
        )
        start_actions = (
            f'<a class="action-link" href="#recipe-{_escape(recipe_id)}">Open this setup</a>'
            f'<a class="action-link" href="{_escape(f"{registry_prefix}/install/{_slug(tool_name)}")}">Open setup data</a>'
        )

    trust = detail.get("trust_score") or {}
    confidence = _percent(trust.get("overall"))

    return f"""
    <section class="panel" style="margin-top: 18px;">
      <div class="panel-head">
        <div>
          <h2>Get oriented quickly</h2>
          <div class="subtle">The shortest path to deciding whether this tool is right for you.</div>
        </div>
      </div>
      <div class="pathway-grid">
        <div class="section-card is-accent">
          <div class="section-kicker">Fastest start</div>
          <h3>{_escape(start_title)}</h3>
          <div class="detail-note" style="margin-top: 10px;">{_escape(start_body)}</div>
          <div class="quick-link-grid">{start_actions}</div>
        </div>
        <div class="section-card">
          <div class="section-kicker">What this tool touches</div>
          <h3>Access and setup snapshot</h3>
          <ul class="checklist">
            <li>{permission_count} declared permission{"s" if permission_count != 1 else ""}</li>
            <li>{resource_count} connected source{"s" if resource_count != 1 else ""}</li>
            <li>{data_flow_count} data flow{"s" if data_flow_count != 1 else ""}</li>
          </ul>
        </div>
        <div class="section-card">
          <div class="section-kicker">Who shared it</div>
          <h3>Publisher and fit</h3>
          <div class="detail-note" style="margin-top: 10px;">
            Shared by <a href="{_escape(publisher_href)}">{_escape(detail.get("author") or "unknown publisher")}</a> with confidence {confidence}.
          </div>
          <div class="chip-row" style="margin-top: 12px;">{_render_chip_row(categories)}</div>
        </div>
      </div>
    </section>
    """


def _render_publisher_experience_cards(
    *,
    registry_prefix: str,
    summary: dict[str, Any],
    listings: list[dict[str, Any]],
) -> str:
    top_links = (
        "".join(
            f'<a class="action-link" href="{_escape(_tool_href(registry_prefix=registry_prefix, tool_name=str(listing.get("tool_name", "")), query="", min_certification=""))}">{_escape(listing.get("display_name") or listing.get("tool_name") or "Open tool")}</a>'
            for listing in listings[:3]
        )
        if listings
        else '<div class="detail-note">No live tools are available to open yet.</div>'
    )

    return f"""
    <section class="panel" style="margin-top: 18px;">
      <div class="panel-head">
        <div>
          <h2>Start with this publisher</h2>
          <div class="subtle">A quicker way to understand what this publisher is known for and where to begin.</div>
        </div>
      </div>
      <div class="pathway-grid">
        <div class="section-card is-accent">
          <div class="section-kicker">Best first click</div>
          <h3>Open one of their live tools</h3>
          <div class="detail-note" style="margin-top: 10px;">
            If you want the fastest sense of this publisher, start with one of the live tool pages below.
          </div>
          <div class="quick-link-grid">{top_links}</div>
        </div>
        <div class="section-card">
          <div class="section-kicker">What they focus on</div>
          <h3>Topics and strengths</h3>
          <div class="chip-row" style="margin-top: 12px;">{_render_chip_row(list(summary.get("categories") or []))}</div>
          <div class="field-hint">Keywords: {_escape(", ".join(summary.get("tags") or []) or "none yet")}</div>
        </div>
        <div class="section-card">
          <div class="section-kicker">Trust snapshot</div>
          <h3>How active they are here</h3>
          <ul class="checklist">
            <li>{_escape(summary.get("listing_count", 0))} live tool{"s" if summary.get("listing_count", 0) != 1 else ""}</li>
            <li>Average confidence {_percent(summary.get("average_trust"))}</li>
            <li>Latest update {_escape(summary.get("latest_activity") or "n/a")}</li>
          </ul>
        </div>
      </div>
    </section>
    """


def _render_get_started_overview(*, registry_prefix: str) -> str:
    return f"""
    <div class="story-grid">
      <div class="story-card">
        <div class="section-kicker">Step 1</div>
        <strong>Pick a tool that sounds useful</strong>
        <p>Start with the problem you want to solve, not the protocol details. Tool cards are written to be scannable.</p>
        <div class="quick-link-grid">
          <a class="action-link" href="#catalog">Browse tools</a>
        </div>
      </div>
      <div class="story-card">
        <div class="section-kicker">Step 2</div>
        <strong>Open the full tool page</strong>
        <p>The tool page tells you what it helps with, who shared it, and the fastest way to get started.</p>
      </div>
      <div class="story-card">
        <div class="section-kicker">Step 3</div>
        <strong>Copy the setup that fits</strong>
        <p>Every good listing leads with the easiest setup path first, then keeps the deeper details lower on the page.</p>
        <div class="quick-link-grid">
          <a class="action-link" href="{_escape(registry_prefix)}#catalog">Find setup-ready tools</a>
        </div>
      </div>
    </div>
    """


def _render_start_using_choices(install_recipes: list[dict[str, Any]]) -> str:
    if not install_recipes:
        return """
        <div class="section-card">
          <h3>Setup is still on the way</h3>
          <div class="detail-note" style="margin-top: 10px;">
            The publisher has not added ready-to-copy setup steps yet.
          </div>
        </div>
        """

    cards: list[str] = []
    for index, recipe in enumerate(install_recipes[:3], start=1):
        recipe_id = _slug(str(recipe.get("recipe_id") or index))
        cards.append(
            f"""
            <article class="section-card">
              <h3>{_escape(recipe.get("title", "Setup option"))}</h3>
              <div class="detail-note" style="margin-top: 10px;">
                {_escape(recipe.get("description", "Use this setup option to get started quickly."))}
              </div>
              <div class="action-row" style="margin-top: 12px;">
                <a class="action-link" href="#recipe-{recipe_id}">Open this setup</a>
              </div>
            </article>
            """
        )

    if len(install_recipes) > 3:
        cards.append(
            """
            <article class="section-card">
              <h3>Need another path?</h3>
              <div class="detail-note" style="margin-top: 10px;">
                More setup choices are available lower on this page, including verification and advanced connection details.
              </div>
              <div class="action-row" style="margin-top: 12px;">
                <a class="action-link" href="#all-setup-options">See all setup choices</a>
              </div>
            </article>
            """
        )

    return f'<div class="launchpad-grid">{"".join(cards)}</div>'


def _render_featured_publishers(
    *,
    registry_prefix: str,
    publishers: dict[str, Any],
) -> str:
    items = list(publishers.get("publishers") or [])
    if not items:
        return '<div class="empty">No publisher pages are available yet.</div>'

    return "".join(
        f"""
        <article class="publisher-card">
          <div class="catalog-row">
            <strong><a href="{_escape(_publisher_href(registry_prefix=registry_prefix, publisher_id=str(item.get("publisher_id", ""))))}">{_escape(item.get("display_name") or item.get("publisher_id"))}</a></strong>
            <span class="pill">{_escape(item.get("listing_count", 0))} tools</span>
          </div>
          <div class="catalog-meta">
            confidence {_percent(item.get("average_trust"))} ·
            updated {_escape(item.get("latest_activity") or "n/a")}
          </div>
          <div class="detail-note" style="margin-top: 10px;">Topics: {_escape(", ".join(item.get("categories") or []) or "none")}</div>
          <div class="detail-note">Keywords: {_escape(", ".join(item.get("tags") or []) or "none")}</div>
          <div class="action-row" style="margin-top: 12px;">
            <a class="action-link" href="{_escape(_publisher_href(registry_prefix=registry_prefix, publisher_id=str(item.get("publisher_id", ""))))}">View publisher</a>
          </div>
        </article>
        """
        for item in items
    )


def _render_publish_primary_paths(
    *,
    registry_prefix: str,
    auth_enabled: bool,
    session: dict[str, Any] | None,
) -> str:
    if not auth_enabled:
        publish_title = "You can publish from this page"
        publish_body = (
            "Open the form, run the checks, and share when the draft feels clear."
        )
        publish_actions = (
            '<a class="action-link" href="#publish-form">Open the form</a>'
            '<a class="action-link" href="#preflight">See the checks</a>'
        )
    elif session is None:
        publish_title = "You can prepare everything before signing in"
        publish_body = "Fill in the page and run the checks now. Sign in only when you are ready to publish."
        publish_actions = (
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Sign in</a>'
            '<a class="action-link" href="#publish-form">Start with the form</a>'
        )
    elif session.get("can_submit"):
        publish_title = "This account can publish"
        publish_body = (
            "You can move from draft to live page here without leaving the launchpad."
        )
        publish_actions = (
            '<a class="action-link" href="#publish-form">Finish the draft</a>'
            '<a class="action-link" href="#preflight">Open check results</a>'
        )
    else:
        publish_title = "This account can preview, but not publish"
        publish_body = "Use the page to learn the workflow, then switch to a publisher, reviewer, or admin account when it is time to share."
        publish_actions = (
            f'<a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Switch account</a>'
            '<a class="action-link" href="#preflight">See the checks</a>'
        )

    return f"""
    <section class="panel" style="margin-top: 18px;">
      <div class="panel-head">
        <div>
          <h2>What happens on this page?</h2>
          <div class="subtle">A simple view of the whole publisher workflow before you touch the form.</div>
        </div>
      </div>
      <div class="decision-grid">
        <div class="decision-card is-primary">
          <div class="section-kicker">Start</div>
          <strong>Pick a ready-made example</strong>
          <p>Most people start from a preset, then adjust the wording and setup details to match their own tool.</p>
          <div class="quick-link-grid">
            <a class="action-link" href="#publish-form">Choose a starting point</a>
          </div>
        </div>
        <div class="decision-card">
          <div class="section-kicker">Middle</div>
          <strong>Fill in what people need</strong>
          <p>You only need three kinds of information: the page basics, one real setup path, and the detailed record behind the page.</p>
          <div class="simple-list">
            <div class="simple-item">Page basics: name, topics, links, license</div>
            <div class="simple-item">Setup: endpoint, command, or Docker image</div>
            <div class="simple-item">Detailed record: permissions, data sharing, and connected sources</div>
          </div>
        </div>
        <div class="decision-card">
          <div class="section-kicker">Finish</div>
          <strong>{_escape(publish_title)}</strong>
          <p>{_escape(publish_body)}</p>
          <div class="quick-link-grid">{publish_actions}</div>
        </div>
      </div>
    </section>
    """


def _render_publish_preset_cards() -> str:
    return "".join(
        f"""
        <article class="preset-card">
          <div class="catalog-row">
            <strong>{_escape(preset.get("label") or preset_name)}</strong>
            <span class="pill">{_escape(preset.get("requested_level") or "basic")}</span>
          </div>
          <p class="detail-note" style="margin-top: 10px;">
            Start with a ready-made draft for {_escape(preset.get("display_name") or preset_name)}.
          </p>
          <div class="detail-note">Topics: {_escape(preset.get("categories") or "none")}</div>
          <div class="detail-note">Keywords: {_escape(preset.get("tags") or "none")}</div>
          <div class="action-row" style="margin-top: 12px;">
            <button class="button-secondary" type="button" onclick="applyRegistryPreset('{_escape(preset_name)}')">Use this starting point</button>
          </div>
        </article>
        """
        for preset_name, preset in PUBLISHER_PRESETS.items()
    )


def _render_preflight_panel(preflight: dict[str, Any] | None) -> str:
    if not preflight:
        return """
        <div class="section-card">
          <h3>Quick Check</h3>
          <div class="detail-note" style="margin-top: 10px;">
            Run a quick check to spot issues and make sure your tool page will include setup steps before you share it.
          </div>
        </div>
        """

    report = preflight.get("report") or {}
    install_recipes = list(preflight.get("install_recipes") or [])
    findings = list(report.get("findings") or [])
    recipe_list = (
        '<div class="detail-note">No setup steps were detected yet. Add an endpoint, command, or Docker image.</div>'
        if not install_recipes
        else _render_bullet_list(
            [
                f"{item.get('title', item.get('recipe_id', 'recipe'))} ({item.get('format', 'text')})"
                for item in install_recipes
            ]
        )
    )
    finding_list = (
        '<div class="detail-note">No issues were found.</div>'
        if not findings
        else "".join(
            f"""
            <div class="detail-box">
              <div class="label">{_escape(item.get("severity") or "notice")}</div>
              <div class="value">{_escape(item.get("category") or "validation")}</div>
              <div class="detail-note">{_escape(item.get("message") or "No message provided.")}</div>
            </div>
            """
            for item in findings
        )
    )
    return f"""
    <div class="section-card">
      <h3>Quick Check</h3>
      <div class="detail-note" style="margin-top: 10px;">{_escape(preflight.get("summary") or "Your draft looks good.")}</div>
      <div class="detail-grid" style="margin-top: 14px;">
        <div class="detail-box">
          <div class="label">Ready To Share</div>
          <div class="value">{_escape("yes" if preflight.get("ready_for_publish") else "not yet")}</div>
        </div>
        <div class="detail-box">
          <div class="label">Safety Level</div>
          <div class="value">{_escape(preflight.get("effective_certification_level") or "n/a")}</div>
        </div>
        <div class="detail-box">
          <div class="label">Required Minimum</div>
          <div class="value">{_escape(preflight.get("minimum_required_level") or "n/a")}</div>
        </div>
        <div class="detail-box">
          <div class="label">Setup Help</div>
          <div class="value">{_escape("ready" if preflight.get("install_ready") else "not yet")}</div>
        </div>
      </div>
      <div class="detail-note" style="margin-top: 14px;">Internal ID</div>
      <pre class="code-block">{_escape(preflight.get("manifest_digest") or "")}</pre>
      <div class="section-grid" style="margin-top: 14px;">
        <div class="section-card">
          <h3>What People Will See</h3>
          <div class="detail-note" style="margin-top: 10px;">These setup blocks will appear on the public tool page after you share it.</div>
          {recipe_list}
        </div>
        <div class="section-card">
          <h3>Things To Fix</h3>
          <div class="detail-stack" style="margin-top: 10px;">{finding_list}</div>
        </div>
      </div>
    </div>
    """


def _render_publish_form(
    *,
    registry_prefix: str,
    auth_enabled: bool,
    session: dict[str, Any] | None,
    manifest_text: str,
    runtime_metadata_text: str,
    display_name: str,
    categories: str,
    tags: str,
    requested_level: str,
    source_url: str,
    homepage_url: str,
    tool_license: str,
) -> str:
    requested_level_options = "".join(
        f'<option value="{value}"{" selected" if value == requested_level else ""}>{label}</option>'
        for value, label in (
            ("basic", "Basic"),
            ("standard", "Standard"),
            ("strict", "Strict"),
            ("self_attested", "Self Attested"),
        )
    )
    can_submit = not auth_enabled or bool(session and session.get("can_submit"))
    publish_button = (
        '<button type="submit" name="submission_action" value="publish">Share Tool</button>'
        if can_submit
        else '<button type="button" class="button-secondary" disabled>Sign in to share</button>'
    )
    auth_note = ""
    if auth_enabled and session is None:
        auth_note = f"""
        <div class="auth-panel" style="margin-top: 14px;">
          <h3>You can preview first</h3>
          <p class="detail-note" style="margin-top: 10px;">
            You can check this draft now. Sign in when you're ready to share it.
          </p>
          <div class="action-row" style="margin-top: 12px;">
            <a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Sign in</a>
          </div>
        </div>
        """
    elif auth_enabled and session is not None and not session.get("can_submit"):
        auth_note = f"""
        <div class="auth-panel" style="margin-top: 14px;">
          <h3>This account cannot share tools</h3>
          <p class="detail-note" style="margin-top: 10px;">
            Signed in as {_escape(session.get("role") or "viewer")}. Switch to a publisher, reviewer, or admin account when you're ready to share this tool.
          </p>
        </div>
        """

    return f"""
    <form method="post" action="{_escape(_publish_href(registry_prefix=registry_prefix))}" style="margin-top: 14px;">
      <div class="stacked-panels">
        <section class="section-card is-accent">
          <div class="section-kicker">Step 1</div>
          <h3>Choose a starting point</h3>
          <div class="detail-note" style="margin-top: 10px;">
            Start with a ready-made draft so you can shape a good page instead of staring at a blank form.
          </div>
          <div class="preset-grid" style="margin-top: 16px;">
            {_render_publish_preset_cards()}
          </div>
        </section>

        <section class="section-card">
          <div class="section-kicker">Step 2</div>
          <h3>Add the page basics</h3>
          <div class="detail-note" style="margin-top: 10px;">
            These details appear first on the public page, so keep them plain, specific, and easy to scan.
          </div>
          <div class="publish-grid" style="margin-top: 16px;">
            <label class="field-stack">
              <span class="field-label">Public Name</span>
              <input id="publish-display-name" name="display_name" value="{_escape(display_name)}" placeholder="Weather Lookup" />
            </label>
            <label class="field-stack">
              <span class="field-label">Topics People Browse</span>
              <input id="publish-categories" name="categories" value="{_escape(categories)}" placeholder="network,utility" />
            </label>
            <label class="field-stack">
              <span class="field-label">Search Words</span>
              <input id="publish-tags" name="tags" value="{_escape(tags)}" placeholder="weather,api" />
            </label>
            <label class="field-stack">
              <span class="field-label">Requested Review Level</span>
              <select id="publish-requested-level" name="requested_level">{requested_level_options}</select>
            </label>
            <label class="field-stack">
              <span class="field-label">Source Code</span>
              <input id="publish-source-url" name="source_url" value="{_escape(source_url)}" placeholder="https://github.com/acme/weather-lookup" />
            </label>
            <label class="field-stack">
              <span class="field-label">Docs Or Homepage</span>
              <input id="publish-homepage-url" name="homepage_url" value="{_escape(homepage_url)}" placeholder="https://acme.example/weather" />
            </label>
            <label class="field-stack">
              <span class="field-label">License</span>
              <input id="publish-license" name="tool_license" value="{_escape(tool_license)}" placeholder="MIT" />
            </label>
          </div>
          <div class="field-hint">
            Keep these details plain and specific. A good page should make sense to someone in under 30 seconds.
          </div>
        </section>

        <section class="section-card">
          <div class="section-kicker">Step 3</div>
          <h3>Show how people get started</h3>
          <div class="detail-note" style="margin-top: 10px;">
            Add one real setup path here. This is what becomes the ready-to-copy setup block on the public page.
          </div>
          <label class="field-stack" style="margin-top: 14px;">
            <span class="field-label">Setup Details (JSON)</span>
            <textarea id="publish-runtime-metadata" name="runtime_metadata">{_escape(runtime_metadata_text)}</textarea>
          </label>
          <div class="field-hint">
            Include at least one real endpoint, local command, or Docker image so the page shows people how to get started.
          </div>
        </section>

        <section class="section-card">
          <div class="section-kicker">Step 4</div>
          <h3>Add the detailed record</h3>
          <div class="detail-note" style="margin-top: 10px;">
            This fuller record powers review, trust signals, and the deeper details behind the public page.
          </div>
          <label class="field-stack" style="margin-top: 14px;">
            <span class="field-label">Detailed Record (JSON)</span>
            <textarea id="publish-manifest" name="manifest">{_escape(manifest_text)}</textarea>
          </label>
          <div class="field-hint">
            Be accurate about permissions, data sharing, and connected sources. This is where trust gets earned or lost.
          </div>
        </section>

        <section class="section-card">
          <div class="section-kicker">Final step</div>
          <h3>Check, then share</h3>
          <div class="detail-note" style="margin-top: 10px;">
            Run the checks, fix anything unclear, then share when the page feels useful to someone seeing it for the first time.
          </div>
          <ul class="checklist">
            <li>Your summary should be readable without opening the raw JSON.</li>
            <li>You should have at least one genuine setup path in the connection details.</li>
            <li>The detailed record should match what the tool actually does.</li>
          </ul>
          <div class="action-row" style="margin-top: 14px;">
            <button class="button-secondary" type="submit" name="submission_action" value="preview">Preview Checks</button>
            {publish_button}
          </div>
          {auth_note}
        </section>
      </div>
    </form>
    """


def create_registry_ui_html(
    *,
    server_name: str,
    registry_prefix: str = "/registry",
    health: dict[str, Any],
    catalog: dict[str, Any],
    publishers: dict[str, Any],
    queue: dict[str, Any],
    auth_enabled: bool,
    session: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    query: str = "",
    min_certification: str = "",
    manifest_text: str = SAMPLE_MANIFEST_JSON,
    display_name: str = "Weather Lookup",
    categories: str = "network,utility",
    requested_level: str = "basic",
    page_notice_title: str | None = None,
    page_notice_body: str | None = None,
    page_notice_is_error: bool = False,
    submission_title: str | None = None,
    submission_body: str | None = None,
    submission_is_error: bool = False,
) -> str:
    """Render the registry catalog and submission UI."""

    page_title = "PureCipher Secured MCP Registry"
    can_review = _can_review_registry(auth_enabled=auth_enabled, session=session)
    min_level_options = "".join(
        f'<option value="{value}"{" selected" if value == min_certification else ""}>{label}</option>'
        for value, label in (
            ("", "Any safety level"),
            ("basic", "Basic"),
            ("standard", "Standard"),
            ("strict", "Strict"),
        )
    )
    page_notice_html = _render_optional_notice(
        notice_title=page_notice_title,
        notice_body=page_notice_body,
        notice_is_error=page_notice_is_error,
    )
    result_summary_bits = [f"{_escape(catalog.get('count', 0))} tools"]
    if query:
        result_summary_bits.append(f'query "{_escape(query)}"')
    if min_certification:
        result_summary_bits.append(f"min {_escape(min_certification)}")
    result_summary = " · ".join(result_summary_bits)
    publisher_count = int(publishers.get("count", 0) or 0)
    if not auth_enabled:
        submission_panel = f"""
        <div class="section-grid" style="margin-top: 14px;">
          <div class="section-card">
            <h3>Want to share something?</h3>
            <div class="detail-note" style="margin-top: 10px;">
              Open the guided share flow to turn your tool into a clear page with setup steps and trust details.
            </div>
            <div class="action-row" style="margin-top: 12px;">
              <a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Open share flow</a>
            </div>
          </div>
          <div class="section-card">
            <h3>Publishing from scripts?</h3>
            <div class="detail-note" style="margin-top: 10px;">
              The same registry also exposes API endpoints for CI and scripted publishing.
            </div>
            {_render_api_endpoint_details(registry_prefix=registry_prefix)}
          </div>
        </div>
        """
    elif session is None:
        submission_panel = f"""
        <div class="section-grid" style="margin-top: 14px;">
          <div class="section-card">
            <h3>Want to share something?</h3>
            <div class="detail-note" style="margin-top: 10px;">
              You can preview the form now. Sign in when you're ready to share.
            </div>
            <div class="action-row" style="margin-top: 12px;">
              <a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Open share flow</a>
              <a class="action-link" href="{_escape(_login_href(registry_prefix=registry_prefix, next_path=_publish_href(registry_prefix=registry_prefix)))}">Sign in</a>
            </div>
          </div>
          <div class="section-card">
            <h3>What you will need</h3>
            <div class="detail-note" style="margin-top: 10px;">
              Bring your tool details, setup details, source link, and license so people can understand and use your tool right away.
            </div>
          </div>
        </div>
        """
    else:
        submission_panel = f"""
        <div class="section-grid" style="margin-top: 14px;">
          <div class="section-card">
            <h3>Want to share something?</h3>
            <div class="detail-note" style="margin-top: 10px;">
              Signed in as {_escape(session.get("role") or "viewer")}. Use the guided flow to check your draft and share a clear, useful tool page.
            </div>
            <div class="action-row" style="margin-top: 12px;">
              <a class="action-link" href="{_escape(_publish_href(registry_prefix=registry_prefix))}">Open share flow</a>
            </div>
          </div>
          <div class="section-card">
            <h3>Publishing from scripts?</h3>
            <div class="detail-note" style="margin-top: 10px;">
              If you publish from scripts or CI, the same API endpoints are available here too.
            </div>
            {_render_api_endpoint_details(registry_prefix=registry_prefix)}
          </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{page_title}</title>
    <style>{BASE_STYLES}</style>
  </head>
  <body>
    <main class="shell is-login">
      {
        _render_topbar(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            current_page="catalog",
            current_path=registry_prefix,
        )
    }
      <section class="hero">
        <div class="eyebrow">Trusted Tool Directory</div>
        <div class="hero-cluster">
          <div>
            <h1>Find a tool you can trust</h1>
            <p class="subtle" style="margin-top: 8px;">Server: {
        _escape(server_name)
    }</p>
            <p class="hero-copy">
              Open any tool page to understand what it does, who shared it, what it can access, and the easiest way to start using it.
            </p>
            <div class="jump-links">
              <a class="action-link jump-link" href="#catalog">Find a tool</a>
              <a class="action-link jump-link" href="#publishers">Meet the publishers</a>
              <a class="action-link jump-link" href="{
        _escape(_publish_href(registry_prefix=registry_prefix))
    }">Share a tool</a>
            </div>
          </div>
          <div class="metrics">
            <div class="metric">
              <div class="label">Tools live</div>
              <div class="value">{_escape(health.get("verified_tools", 0))}</div>
            </div>
            <div class="metric">
              <div class="label">Publishers</div>
              <div class="value">{_escape(publisher_count)}</div>
            </div>
            <div class="metric">
              <div class="label">Review minimum</div>
              <div class="value">{
        _escape(health.get("minimum_certification", "n/a"))
    }</div>
            </div>
            <div class="metric">
              <div class="label">Waiting</div>
              <div class="value">{_escape(health.get("pending_review", 0))}</div>
            </div>
          </div>
        </div>
	        <div class="footer-links">
	          <a href="{_escape(registry_prefix)}">Browse home</a>
	          <a href="{
        _escape(_publisher_index_href(registry_prefix=registry_prefix))
    }">All publishers</a>
	          <a href="{
        _escape(_publish_href(registry_prefix=registry_prefix))
    }">Share a tool</a>
              {
        f'<a href="{_escape(f"{registry_prefix}/review")}">Approvals</a>'
        if can_review
        else ""
    }
	        </div>
      </section>

      {page_notice_html}

      {
        _render_registry_primary_paths(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
        )
    }

      <section class="panel" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>Start Here</h2>
            <div class="subtle">If you are new here, this is the fastest way to go from “that looks useful” to “I know how to start.”</div>
          </div>
        </div>
        {_render_get_started_overview(registry_prefix=registry_prefix)}
      </section>

      {
        _render_registry_experience_cards(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            catalog=catalog,
            min_certification=min_certification,
        )
    }

      <section class="layout">
        <section class="panel" id="catalog">
          <div class="panel-head">
            <div>
              <h2>Browse Tools</h2>
              <div class="subtle">Search by name, publisher, description, or keywords.</div>
            </div>
          </div>
          <form class="search-form" method="get" action="{_escape(registry_prefix)}">
            <label class="field-stack">
              <span class="field-label">Search</span>
              <input name="q" value="{_escape(query)}" placeholder="Search tools" />
            </label>
            <label class="field-stack">
              <span class="field-label">Safety Level</span>
              <select name="min_certification">{min_level_options}</select>
            </label>
            <button type="submit">Update Results</button>
          </form>
          <div class="results-bar">
            <div class="results-summary">{result_summary}</div>
            <div class="micro-note">Open any card to learn what it does and how to use it.</div>
          </div>
          <div class="catalog">
            {
        _render_catalog(
            registry_prefix=registry_prefix,
            catalog=catalog,
            query=query,
            min_certification=min_certification,
        )
    }
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Overview</h2>
              <div class="subtle">See what is ready to explore, what is still being reviewed, and where to go next.</div>
            </div>
          </div>
          {
        _render_dashboard_snapshot(
            registry_prefix=registry_prefix,
            health=health,
            queue=queue,
            detail=detail,
            query=query,
            min_certification=min_certification,
            can_review=can_review,
        )
    }
        </section>
      </section>

      <section class="panel" id="publishers" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>Featured Publishers</h2>
            <div class="subtle">A quick look at the teams and people behind the tools in this registry.</div>
          </div>
          <a class="action-link" href="{
        _escape(_publisher_index_href(registry_prefix=registry_prefix))
    }">View all publishers</a>
        </div>
        <div class="publisher-highlight-grid">
          {
        _render_featured_publishers(
            registry_prefix=registry_prefix,
            publishers=publishers,
        )
    }
        </div>
      </section>

      <section class="panel" id="submit" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>Share A Tool</h2>
            <div class="subtle">The share flow walks you through the public details, the setup path, and the checks before anything goes live.</div>
          </div>
          <a class="action-link" href="{
        _escape(_publish_href(registry_prefix=registry_prefix))
    }">Open share flow</a>
        </div>
        {
        _render_submission_notice(
            submission_title=submission_title,
            submission_body=submission_body,
            submission_is_error=submission_is_error,
        )
    }
        {submission_panel}
      </section>
    </main>
  </body>
</html>"""


def create_publish_html(
    *,
    server_name: str,
    registry_prefix: str = "/registry",
    auth_enabled: bool,
    session: dict[str, Any] | None = None,
    manifest_text: str = SAMPLE_MANIFEST_JSON,
    runtime_metadata_text: str = SAMPLE_RUNTIME_METADATA_JSON,
    display_name: str = "Weather Lookup",
    categories: str = "network,utility",
    tags: str = "weather,api",
    requested_level: str = "basic",
    source_url: str = "https://github.com/acme/weather-lookup",
    homepage_url: str = "",
    tool_license: str = "MIT",
    preflight: dict[str, Any] | None = None,
    page_notice_title: str | None = None,
    page_notice_body: str | None = None,
    page_notice_is_error: bool = False,
    submission_title: str | None = None,
    submission_body: str | None = None,
    submission_is_error: bool = False,
) -> str:
    """Render the guided publisher launchpad."""

    page_title = "Share A Tool · PureCipher Secured MCP Registry"
    can_review = _can_review_registry(auth_enabled=auth_enabled, session=session)
    page_notice_html = _render_optional_notice(
        notice_title=page_notice_title,
        notice_body=page_notice_body,
        notice_is_error=page_notice_is_error,
    )
    submission_notice_html = _render_submission_notice(
        submission_title=submission_title,
        submission_body=submission_body,
        submission_is_error=submission_is_error,
    )
    auth_summary = (
        "Anyone can preview"
        if not auth_enabled
        else (
            f"Signed in as {session.get('role')}"
            if session is not None
            else "Preview now, sign in to share"
        )
    )
    guidance_summary = (
        "Open share flow"
        if not auth_enabled
        else (
            "Ready to publish"
            if session is not None and session.get("can_submit")
            else "Preview before publish"
        )
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{page_title}</title>
    <style>{BASE_STYLES}</style>
  </head>
  <body>
    <main class="shell is-login">
      {
        _render_topbar(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            current_page="publish",
            current_path=_publish_href(registry_prefix=registry_prefix),
        )
    }
      <section class="hero">
        <div class="eyebrow">Share A Tool</div>
        <div class="hero-cluster">
          <div>
            <h1>Share your tool without guessing</h1>
            <p class="subtle" style="margin-top: 8px;">Server: {
        _escape(server_name)
    }</p>
            <p class="hero-copy">
              This page is built to help you create a tool page people can understand quickly: what it does, how to start, and what it can access.
            </p>
            <div class="jump-links">
              <a class="action-link jump-link" href="#launchpad">See the flow</a>
              <a class="action-link jump-link" href="#publish-form">Open the form</a>
              <a class="action-link jump-link" href="#preflight">Review checks</a>
            </div>
          </div>
          <div class="metrics">
            <div class="metric">
              <div class="label">Access</div>
              <div class="value">{_escape(auth_summary)}</div>
            </div>
            <div class="metric">
              <div class="label">What you do here</div>
              <div class="value">{_escape(guidance_summary)}</div>
            </div>
            <div class="metric">
              <div class="label">Checks</div>
              <div class="value">Built in</div>
            </div>
            <div class="metric">
              <div class="label">Starter Example</div>
              <div class="value">Remote HTTP</div>
            </div>
          </div>
        </div>
	        <div class="footer-links">
	          <a href="{_escape(registry_prefix)}">Browse home</a>
	          <a href="{
        _escape(_publish_href(registry_prefix=registry_prefix))
    }">Share form</a>
              {
        f'<a href="{_escape(f"{registry_prefix}/review")}">Approvals</a>'
        if can_review
        else ""
    }
	          <a href="{
        _escape(_publisher_index_href(registry_prefix=registry_prefix))
    }">Browse publishers</a>
	        </div>
      </section>

      {page_notice_html}

      {
        _render_publish_primary_paths(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
        )
    }

      <section class="panel" id="launchpad" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>Start Here</h2>
            <div class="subtle">If you are new to publishing, this is the simplest way to think about the workflow.</div>
          </div>
        </div>
        <div class="launchpad-grid">
          <div class="section-card">
            <h3>1. Pick a starting point</h3>
            <div class="detail-note" style="margin-top: 10px;">
              Choose a ready-made example so you do not have to start from a blank page.
            </div>
          </div>
          <div class="section-card">
            <h3>2. Check it</h3>
            <div class="detail-note" style="margin-top: 10px;">
              See likely issues and make sure people will get clear setup steps before anything goes live.
            </div>
          </div>
          <div class="section-card">
            <h3>3. Share it</h3>
            <div class="detail-note" style="margin-top: 10px;">
              When it looks good, share it here. If you automate this, the developer endpoint uses the same data.
            </div>
          </div>
        </div>
      </section>

      {
        _render_publish_experience_cards(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            preflight=preflight,
        )
    }

      <section class="layout">
        <section class="panel" id="publish-form">
          <div class="panel-head">
            <div>
              <h2>Share Form</h2>
              <div class="subtle">Add the details people need to understand and use your tool.</div>
            </div>
          </div>
          {submission_notice_html}
          {
        _render_publish_form(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            manifest_text=manifest_text,
            runtime_metadata_text=runtime_metadata_text,
            display_name=display_name,
            categories=categories,
            tags=tags,
            requested_level=requested_level,
            source_url=source_url,
            homepage_url=homepage_url,
            tool_license=tool_license,
        )
    }
        </section>

        <section class="panel" id="preflight">
          <div class="panel-head">
            <div>
              <h2>Check Results</h2>
              <div class="subtle">A quick readiness check for your current draft.</div>
            </div>
          </div>
          {_render_preflight_panel(preflight)}
        </section>
      </section>

      <section class="panel" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>For scripts and CI</h2>
            <div class="subtle">The browser flow and the API use the same registry logic, so automation is available when you need it.</div>
          </div>
        </div>
        {_render_api_endpoint_details(registry_prefix=registry_prefix)}
      </section>
      {LISTING_INTERACTIONS_SCRIPT}
    </main>
  </body>
</html>"""


def create_listing_detail_html(
    *,
    server_name: str,
    registry_prefix: str,
    detail: dict[str, Any],
    install_recipes: list[dict[str, Any]],
    auth_enabled: bool,
    session: dict[str, Any] | None = None,
    query: str = "",
    min_certification: str = "",
) -> str:
    """Render a dedicated listing page with install and attestation detail."""

    page_title = "PureCipher Secured MCP Registry"
    tool_name = str(detail.get("tool_name") or "")
    display_name = str(detail.get("display_name") or tool_name)
    publisher_id = str(detail.get("publisher_id") or "")
    publisher_name = str(detail.get("author") or "unknown")
    manifest = detail.get("manifest") or {}
    attestation = detail.get("attestation") or {}
    trust = detail.get("trust_score") or {}
    verification = detail.get("verification") or {}
    categories = sorted(detail.get("categories") or [])
    tags = sorted(detail.get("tags") or [])
    back_href = _catalog_href(
        registry_prefix=registry_prefix,
        query=query,
        min_certification=min_certification,
    )
    publisher_href = _publisher_href(
        registry_prefix=registry_prefix,
        publisher_id=publisher_id,
    )
    install_href = f"{registry_prefix}/install/{_slug(tool_name)}"
    detail_api_href = f"{registry_prefix}/tools/{_slug(tool_name)}"
    manifest_json = _pretty_json(manifest)
    attestation_json = _pretty_json(attestation)
    install_bundle = "\n\n".join(
        [
            f"# {recipe.get('title', 'Install Recipe')}\n{recipe.get('content', '')}"
            for recipe in install_recipes
        ]
    )
    recipe_overview = (
        "".join(
            f'<a class="action-link jump-link" href="#recipe-{_slug(str(recipe.get("recipe_id") or index))}">{_escape(recipe.get("title", "Recipe"))}</a>'
            for index, recipe in enumerate(install_recipes, start=1)
        )
        if install_recipes
        else ""
    )
    recipe_html = (
        "".join(
            f"""
            <article class="recipe" id="recipe-{
                _slug(str(recipe.get("recipe_id") or index))
            }">
              <div class="recipe-head">
                <div>
                  <h3>{_escape(recipe.get("title", "Install Recipe"))}</h3>
                  <div class="recipe-summary">{
                _escape(recipe.get("description", ""))
            }</div>
                </div>
                <div class="recipe-actions">
                  <span class="pill">{_escape(recipe.get("format", "text"))}</span>
                  {
                _render_copy_button(
                    target_id=f"recipe-code-{index}",
                    label="Copy recipe",
                )
            }
                </div>
              </div>
              <pre class="code-block" id="recipe-code-{index}">{
                _escape(recipe.get("content", ""))
            }</pre>
            </article>
            """
            for index, recipe in enumerate(install_recipes, start=1)
        )
        if install_recipes
        else '<div class="empty">No setup details have been added for this tool yet.</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{display_name} · {page_title}</title>
    <style>{BASE_STYLES}</style>
  </head>
  <body>
    <main class="shell">
      {
        _render_topbar(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            current_page="catalog",
            current_path=_tool_href(
                registry_prefix=registry_prefix,
                tool_name=tool_name,
                query=query,
                min_certification=min_certification,
            ),
        )
    }
      <section class="hero">
        <div class="eyebrow">Trusted Tool</div>
        <h1>{_escape(display_name)}</h1>
        <p class="subtle" style="margin-top: 8px;">Server: {
        _escape(server_name)
    } · Publisher: <a href="{_escape(publisher_href)}">{_escape(publisher_name)}</a></p>
        <p class="hero-copy">{
        _escape(detail.get("description") or "No description provided.")
    }</p>
        <div class="jump-links">
          <span class="listing-chip">{
        _escape(detail.get("certification_level") or "uncertified")
    }</span>
          <span class="listing-chip">confidence {_percent(trust.get("overall"))}</span>
          <span class="listing-chip">v{_escape(detail.get("version") or "0.0.0")}</span>
        </div>
        <div class="hero-actions">
          <a class="action-link" href="{_escape(back_href)}">Back to browse</a>
          <a class="action-link" href="{_escape(publisher_href)}">Publisher</a>
          <a class="action-link" href="{_escape(detail_api_href)}">Raw data</a>
          <a class="action-link" href="{_escape(install_href)}">Setup data</a>
        </div>
        <div class="metrics">
          <div class="metric">
            <div class="label">Safety Level</div>
            <div class="value">{
        _escape(detail.get("certification_level") or "uncertified")
    }</div>
          </div>
          <div class="metric">
            <div class="label">Confidence</div>
            <div class="value">{_percent(trust.get("overall"))}</div>
          </div>
          <div class="metric">
            <div class="label">Uses</div>
            <div class="value">{_escape(detail.get("active_installs") or 0)}</div>
          </div>
          <div class="metric">
            <div class="label">Checks</div>
            <div class="value">{
        "looks good" if verification.get("valid") else "needs attention"
    }</div>
          </div>
        </div>
      </section>

      {
        _render_listing_experience_cards(
            registry_prefix=registry_prefix,
            detail=detail,
            install_recipes=install_recipes,
            publisher_href=publisher_href,
        )
    }

      <section class="page-stack">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Why People Choose It</h2>
              <div class="subtle">A quick summary for deciding whether this tool feels like the right fit.</div>
            </div>
          </div>
          <div class="launchpad-grid">
            <div class="section-card">
              <h3>What it helps with</h3>
              <div class="detail-note" style="margin-top: 10px;">{
        _escape(
            detail.get("description") or "The publisher has not added a summary yet."
        )
    }</div>
            </div>
            <div class="section-card">
              <h3>Good fit for</h3>
              <div class="detail-note" style="margin-top: 10px;">
                Browse the topics below if you want a fast sense of where this tool is most useful.
              </div>
              <div class="chip-row" style="margin-top: 12px;">{
        _render_chip_row(categories or tags)
    }</div>
            </div>
            <div class="section-card">
              <h3>Before you connect</h3>
              <div class="detail-note" style="margin-top: 10px;">
                Shared by <a href="{_escape(publisher_href)}">{
        _escape(publisher_name)
    }</a>, reviewed at {
        _escape(detail.get("certification_level") or "unreviewed")
    }, and currently showing confidence {_percent(trust.get("overall"))}.
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Start Here</h2>
              <div class="subtle">Pick the setup path that feels simplest, then scroll down for the ready-to-copy steps.</div>
            </div>
          </div>
          {_render_start_using_choices(install_recipes)}
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>What You Should Know</h2>
              <div class="subtle">Who made this tool, where to find it, and where to learn more.</div>
            </div>
          </div>
          <div class="section-grid">
            <div class="section-card">
              <h3>About This Tool</h3>
              <dl class="definition-grid">
                <dt>Tool Name</dt>
                <dd>{_escape(tool_name)}</dd>
                <dt>Version</dt>
                <dd>{_escape(detail.get("version") or "0.0.0")}</dd>
                <dt>Publisher</dt>
                <dd><a href="{_escape(publisher_href)}">{
        _escape(publisher_name)
    }</a></dd>
                <dt>License</dt>
                <dd>{_escape(detail.get("license") or "unlisted")}</dd>
                <dt>Source</dt>
                <dd>{
        f'<a href="{_escape(detail["source_url"])}">{_escape(detail["source_url"])}</a>'
        if detail.get("source_url")
        else "unlisted"
    }</dd>
                <dt>Homepage</dt>
                <dd>{
        f'<a href="{_escape(detail["homepage_url"])}">{_escape(detail["homepage_url"])}</a>'
        if detail.get("homepage_url")
        else "unlisted"
    }</dd>
              </dl>
            </div>
            <div class="section-card">
              <h3>How People Find It</h3>
              <div class="label">Topics</div>
              <div class="chip-row" style="margin-top: 10px;">{
        _render_chip_row(categories)
    }</div>
              <div class="label" style="margin-top: 16px;">Keywords</div>
              <div class="chip-row" style="margin-top: 10px;">{
        _render_chip_row(tags)
    }</div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>What This Tool Needs</h2>
              <div class="subtle">What the publisher says this tool can access, share, and connect to.</div>
            </div>
          </div>
          <div class="section-grid">
            <div class="section-card">
              <h3>Permissions</h3>
              {_render_bullet_list(sorted(manifest.get("permissions") or []))}
              <dl class="definition-grid">
                <dt>Same Result Each Time</dt>
                <dd>{_escape(manifest.get("idempotent", False))}</dd>
                <dt>Predictable Output</dt>
                <dd>{_escape(manifest.get("deterministic", False))}</dd>
                <dt>Needs Approval</dt>
                <dd>{_escape(manifest.get("requires_consent", False))}</dd>
                <dt>Time Limit</dt>
                <dd>{_escape(manifest.get("max_execution_time_seconds", "n/a"))}s</dd>
              </dl>
            </div>
            <div class="section-card">
              <h3>Data Sharing</h3>
              <div class="detail-stack">{_render_data_flows(manifest)}</div>
            </div>
          </div>
          <div class="section-card" style="margin-top: 12px;">
            <h3>Connected Sources</h3>
            <div class="detail-stack">{_render_resource_access(manifest)}</div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Why It Feels Safe</h2>
              <div class="subtle">The checks PureCipher saved for this tool, in plain language first.</div>
            </div>
          </div>
          <div class="section-grid">
            <div class="section-card">
              <h3>Review Summary</h3>
              <dl class="definition-grid">
                <dt>Checked By</dt>
                <dd>{_escape(attestation.get("issuer_id") or "unknown")}</dd>
                <dt>Status</dt>
                <dd>{_escape(attestation.get("status") or "unknown")}</dd>
                <dt>Issued</dt>
                <dd>{_escape(attestation.get("issued_at") or "n/a")}</dd>
                <dt>Expires</dt>
                <dd>{_escape(attestation.get("expires_at") or "n/a")}</dd>
                <dt>Reference ID</dt>
                <dd><code>{
        _escape(attestation.get("manifest_digest") or "n/a")
    }</code></dd>
              </dl>
            </div>
            <div class="section-card">
              <h3>Notes</h3>
              <ul class="issue-list">{_render_verification_issues(verification)}</ul>
            </div>
          </div>
        </section>

        <section class="panel">
          <div id="all-setup-options"></div>
          <div class="panel-head">
            <div>
              <h2>Ways To Use This Tool</h2>
              <div class="subtle">Copy the setup steps that match the way you want to use this tool.</div>
            </div>
            <div class="recipe-actions">
              {
        _render_copy_button(target_id="install-bundle", label="Copy all setup steps")
    }
              <a class="action-link" href="{_escape(install_href)}">Setup data</a>
            </div>
          </div>
          <div class="recipe-overview">
            {recipe_overview}
          </div>
          <div class="micro-note" style="margin-bottom: 14px;">
            {len(install_recipes)} ready-to-copy setup option{
        "s" if len(install_recipes) != 1 else ""
    } for this tool.
          </div>
          <pre class="copy-source" id="install-bundle">{_escape(install_bundle)}</pre>
          <div class="install-grid">{recipe_html}</div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Advanced Details</h2>
              <div class="subtle">Full saved records for people who want the exact underlying data.</div>
            </div>
            <div class="recipe-actions">
              {_render_copy_button(target_id="manifest-json", label="Copy tool JSON")}
              {
        _render_copy_button(target_id="attestation-json", label="Copy proof JSON")
    }
            </div>
          </div>
          <div class="manifest-columns">
            <div>
              <h3>Tool JSON</h3>
              <pre class="code-block" id="manifest-json">{_escape(manifest_json)}</pre>
            </div>
            <div>
              <h3>Proof JSON</h3>
              <pre class="code-block" id="attestation-json">{
        _escape(attestation_json)
    }</pre>
            </div>
          </div>
        </section>
      </section>
      {LISTING_INTERACTIONS_SCRIPT}
    </main>
  </body>
</html>"""


def _render_review_item(item: dict[str, Any], *, registry_prefix: str) -> str:
    tool_href = _tool_href(
        registry_prefix=registry_prefix,
        tool_name=str(item.get("tool_name", "")),
        query="",
        min_certification="",
    )
    publisher_href = _publisher_href(
        registry_prefix=registry_prefix,
        publisher_id=str(item.get("publisher_id", "")),
    )
    listing_id = _escape(item.get("listing_id", ""))
    actions = list(item.get("available_actions") or [])
    if not actions:
        action_buttons = (
            '<div class="detail-note">No actions are available right now.</div>'
        )
    else:
        action_buttons = "".join(
            f'<button type="submit" formaction="{_escape(f"{registry_prefix}/review/{listing_id}/{action}")}">{_escape(action.replace("-", " ").title())}</button>'
            for action in actions
        )

    return f"""
    <article class="moderation-card">
      <div class="catalog-row">
        <strong><a href="{_escape(tool_href)}">{_escape(item.get("display_name") or item.get("tool_name"))}</a></strong>
        <span class="pill">{_escape(item.get("status") or "unknown")}</span>
      </div>
      <div class="catalog-meta">
        <a href="{_escape(publisher_href)}">{_escape(item.get("author") or "unknown author")}</a> ·
        v{_escape(item.get("version") or "0.0.0")} ·
        confidence {_percent(item.get("trust_score"))}
      </div>
      <div class="detail-note" style="margin-top: 10px;">
        Safety level: {_escape(item.get("certification_level") or "uncertified")} ·
        Updated: {_escape(item.get("updated_at") or "n/a")}
      </div>
      <form class="moderation-form" method="post" action="{_escape(f"{registry_prefix}/review/{listing_id}/{actions[0] if actions else 'approve'}")}">
        <input name="moderator_id" value="purecipher-admin" placeholder="Reviewed by" />
        <input name="reason" placeholder="What changed?" />
        <div class="moderation-actions">{action_buttons}</div>
      </form>
    </article>
    """


def _render_review_section(
    *,
    title: str,
    subtitle: str,
    items: list[dict[str, Any]],
    registry_prefix: str,
) -> str:
    rendered_items = (
        "".join(
            _render_review_item(item, registry_prefix=registry_prefix) for item in items
        )
        if items
        else '<div class="empty">Nothing to show in this section right now.</div>'
    )
    return f"""
    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>{_escape(title)}</h2>
          <div class="subtle">{_escape(subtitle)}</div>
        </div>
      </div>
      <div class="queue-section-grid">{rendered_items}</div>
    </section>
    """


def create_publisher_index_html(
    *,
    server_name: str,
    registry_prefix: str,
    publishers: dict[str, Any],
    auth_enabled: bool,
    session: dict[str, Any] | None = None,
) -> str:
    """Render the publisher directory page."""

    page_title = "PureCipher Secured MCP Registry"
    items = list(publishers.get("publishers") or [])
    publisher_cards = (
        "".join(
            f"""
            <article class="publisher-card">
              <div class="catalog-row">
                <strong><a href="{_escape(_publisher_href(registry_prefix=registry_prefix, publisher_id=str(item.get("publisher_id", ""))))}">{_escape(item.get("display_name") or item.get("publisher_id"))}</a></strong>
                <span class="pill">{_escape(item.get("listing_count", 0))} tools</span>
              </div>
              <div class="catalog-meta">
                confidence {_percent(item.get("average_trust"))} ·
                updated {_escape(item.get("latest_activity") or "n/a")}
              </div>
              <div class="detail-note" style="margin-top: 10px;">Topics: {_escape(", ".join(item.get("categories") or []) or "none")}</div>
              <div class="detail-note">Keywords: {_escape(", ".join(item.get("tags") or []) or "none")}</div>
              <div class="action-row" style="margin-top: 12px;">
                <a class="action-link" href="{_escape(_publisher_href(registry_prefix=registry_prefix, publisher_id=str(item.get("publisher_id", ""))))}">Open publisher</a>
              </div>
            </article>
            """
            for item in items
        )
        if items
        else '<div class="empty">No publisher profiles are available yet.</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Publishers · {page_title}</title>
    <style>{BASE_STYLES}</style>
  </head>
  <body>
    <main class="shell">
      {
        _render_topbar(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            current_page="publishers",
            current_path=_publisher_index_href(registry_prefix=registry_prefix),
        )
    }
      <section class="hero">
        <div class="eyebrow">Publishers</div>
        <h1>People and teams behind the tools</h1>
        <p class="subtle" style="margin-top: 8px;">Server: {
        _escape(server_name)
    } · Profiles: {_escape(publishers.get("count", 0))}</p>
        <p class="hero-copy">
          Explore the people and teams behind the tools in this directory, then open each publisher page to see what they offer.
        </p>
        <div class="hero-actions">
          <a class="action-link" href="{_escape(registry_prefix)}">Back to browse</a>
          <a class="action-link" href="{
        _escape(f"{registry_prefix}/publishers")
    }">Publisher data</a>
        </div>
      </section>

      <section class="panel" style="margin-top: 18px;">
        <div class="panel-head">
          <div>
            <h2>Featured Publishers</h2>
            <div class="subtle">A quick look at the people and teams sharing tools here.</div>
          </div>
        </div>
        <div class="publisher-directory">{publisher_cards}</div>
      </section>
    </main>
  </body>
</html>"""


def create_publisher_profile_html(
    *,
    server_name: str,
    registry_prefix: str,
    profile: dict[str, Any],
    auth_enabled: bool,
    session: dict[str, Any] | None = None,
) -> str:
    """Render a public publisher profile page."""

    page_title = "PureCipher Secured MCP Registry"
    listings = list(profile.get("listings") or [])
    summary = profile
    catalog = {"tools": listings}
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_escape(summary.get("display_name") or "Publisher")} · {page_title}</title>
    <style>{BASE_STYLES}</style>
  </head>
  <body>
    <main class="shell">
      {
        _render_topbar(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            current_page="publishers",
            current_path=_publisher_href(
                registry_prefix=registry_prefix,
                publisher_id=str(summary.get("publisher_id") or ""),
            ),
        )
    }
      <section class="hero">
        <div class="eyebrow">Publisher Profile</div>
        <h1>{_escape(summary.get("display_name") or "Unknown Publisher")}</h1>
        <p class="subtle" style="margin-top: 8px;">Server: {
        _escape(server_name)
    } · Publisher ID: {_escape(summary.get("publisher_id") or "unknown")}</p>
        <p class="hero-copy">
          Learn more about the publisher behind these tools and browse the tools they currently have live.
        </p>
        <div class="hero-actions">
          <a class="action-link" href="{_escape(registry_prefix)}">Back to browse</a>
          <a class="action-link" href="{
        _escape(_publisher_index_href(registry_prefix=registry_prefix))
    }">All publishers</a>
          <a class="action-link" href="{
        _escape(f"{registry_prefix}/publishers")
    }">Publisher data</a>
        </div>
        <div class="jump-links">
          <span class="listing-chip">{
        _escape(summary.get("listing_count", 0))
    } tools</span>
          <span class="listing-chip">confidence {
        _percent(summary.get("average_trust"))
    }</span>
          <span class="listing-chip">{
        _escape(summary.get("publisher_id") or "unknown")
    }</span>
        </div>
        <div class="metrics">
          <div class="metric">
            <div class="label">Live Tools</div>
            <div class="value">{_escape(summary.get("listing_count", 0))}</div>
          </div>
          <div class="metric">
            <div class="label">Average Confidence</div>
            <div class="value">{_percent(summary.get("average_trust"))}</div>
          </div>
          <div class="metric">
            <div class="label">Categories</div>
            <div class="value">{_escape(len(summary.get("categories") or []))}</div>
          </div>
          <div class="metric">
            <div class="label">Latest Update</div>
            <div class="value">{_escape(summary.get("latest_activity") or "n/a")}</div>
          </div>
        </div>
      </section>

      {
        _render_publisher_experience_cards(
            registry_prefix=registry_prefix,
            summary=summary,
            listings=listings,
        )
    }

      <section class="page-stack">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>At A Glance</h2>
              <div class="subtle">A simple summary of this publisher and the tools they share.</div>
            </div>
          </div>
          <div class="section-grid">
            <div class="section-card">
              <h3>Categories</h3>
              <div class="chip-row" style="margin-top: 10px;">{
        _render_chip_row(list(summary.get("categories") or []))
    }</div>
            </div>
            <div class="section-card">
              <h3>Tags</h3>
              <div class="chip-row" style="margin-top: 10px;">{
        _render_chip_row(list(summary.get("tags") or []))
    }</div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Live Tools</h2>
              <div class="subtle">The tools this publisher currently has live in the directory.</div>
            </div>
          </div>
          <div class="publisher-grid">
            {
        _render_catalog(
            registry_prefix=registry_prefix,
            catalog=catalog,
            query="",
            min_certification="",
        )
    }
          </div>
        </section>
      </section>
    </main>
  </body>
</html>"""


def create_review_queue_html(
    *,
    server_name: str,
    registry_prefix: str,
    queue: dict[str, Any],
    auth_enabled: bool,
    session: dict[str, Any] | None = None,
    notice_title: str | None = None,
    notice_body: str | None = None,
    notice_is_error: bool = False,
) -> str:
    """Render the moderation queue page."""

    sections = queue.get("sections") or {}
    counts = queue.get("counts") or {}
    page_title = "PureCipher Secured MCP Registry"
    notice_html = _render_optional_notice(
        notice_title=notice_title,
        notice_body=notice_body,
        notice_is_error=notice_is_error,
    )
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Approvals · {page_title}</title>
    <style>{BASE_STYLES}</style>
  </head>
  <body>
    <main class="shell">
      {
        _render_topbar(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            current_page="review",
            current_path=f"{registry_prefix}/review",
        )
    }
      <section class="hero">
        <div class="eyebrow">Approvals</div>
        <h1>Review shared tools</h1>
        <p class="subtle" style="margin-top: 8px;">Server: {
        _escape(server_name)
    } · Require moderation: {_escape(queue.get("require_moderation", False))}</p>
        <p class="hero-copy">
          Review new submissions, manage live tools, and pause tools when they need attention.
        </p>
        <div class="hero-actions">
          <a class="action-link" href="{_escape(registry_prefix)}">Back to browse</a>
          <a class="action-link" href="{
        _escape(f"{registry_prefix}/review/submissions")
    }">Queue data</a>
        </div>
        <div class="metrics">
          <div class="metric">
            <div class="label">Waiting For Approval</div>
            <div class="value">{_escape(counts.get("pending_review", 0))}</div>
          </div>
          <div class="metric">
            <div class="label">Live</div>
            <div class="value">{_escape(counts.get("published", 0))}</div>
          </div>
          <div class="metric">
            <div class="label">Paused</div>
            <div class="value">{_escape(counts.get("suspended", 0))}</div>
          </div>
          <div class="metric">
            <div class="label">Updated</div>
            <div class="value">{_escape(queue.get("generated_at") or "n/a")}</div>
          </div>
        </div>
      </section>

      <section class="page-stack">
        {notice_html}
        {
        _render_review_section(
            title="Waiting For Approval",
            subtitle="Approve, reject, or ask for changes before a new tool goes live.",
            items=list(sections.get("pending_review") or []),
            registry_prefix=registry_prefix,
        )
    }
        {
        _render_review_section(
            title="Live Tools",
            subtitle="Live tools can still be managed here if they need to be paused.",
            items=list(sections.get("published") or []),
            registry_prefix=registry_prefix,
        )
    }
        {
        _render_review_section(
            title="Paused Tools",
            subtitle="Bring paused tools back when they are ready to go live again.",
            items=list(sections.get("suspended") or []),
            registry_prefix=registry_prefix,
        )
    }
      </section>
    </main>
  </body>
</html>"""


def create_login_html(
    *,
    server_name: str,
    registry_prefix: str,
    auth_enabled: bool,
    session: dict[str, Any] | None = None,
    next_path: str = "/registry",
    notice_title: str | None = None,
    notice_body: str | None = None,
    notice_is_error: bool = False,
) -> str:
    """Render the login page for registry auth."""

    page_title = "PureCipher Secured MCP Registry"
    notice_html = _render_optional_notice(
        notice_title=notice_title,
        notice_body=notice_body,
        notice_is_error=notice_is_error,
    )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Sign In · {page_title}</title>
    <style>{BASE_STYLES}</style>
  </head>
  <body>
    <main class="shell">
      {
        _render_topbar(
            registry_prefix=registry_prefix,
            auth_enabled=auth_enabled,
            session=session,
            current_page="login",
            current_path=_login_href(
                registry_prefix=registry_prefix,
                next_path=next_path,
            ),
        )
    }
      <section class="page-stack">
        {notice_html}
        <section class="panel">
          <div class="login-layout">
            <div class="login-copy">
              <h2>PureCipher Secured MCP Registry</h2>
              <p>Browse trusted tools, see what they can access, and share your own with clear security context.</p>
              <ul class="login-points">
                <li>Verified manifests and attested listings.</li>
                <li>Role-based access for publishers and reviewers.</li>
                <li>Copy‑ready setup for clients, Docker, and CI.</li>
              </ul>
            </div>
            <div class="login-form-wrapper">
              <form class="auth-panel" method="post" action="{
        _escape(f"{registry_prefix}/login")
    }">
              <input type="hidden" name="next" value="{_escape(next_path)}" />
              <label class="detail-note" for="username">Username</label>
              <input id="username" name="username" placeholder="admin" style="margin-top: 8px;" />
              <label class="detail-note" for="password" style="margin-top: 12px; display: block;">Password</label>
              <input id="password" type="password" name="password" placeholder="••••••••" style="margin-top: 8px;" />
              <button type="submit" style="margin-top: 14px;">Sign In</button>
              </form>
            </div>
          </div>
        </section>
      </section>
    </main>
  </body>
</html>"""


__all__ = [
    "SAMPLE_MANIFEST_JSON",
    "SAMPLE_RUNTIME_METADATA_JSON",
    "create_listing_detail_html",
    "create_login_html",
    "create_publish_html",
    "create_publisher_index_html",
    "create_publisher_profile_html",
    "create_registry_ui_html",
    "create_review_queue_html",
]
