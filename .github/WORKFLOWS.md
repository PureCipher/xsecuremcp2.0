# SecureMCP workflow policy

All GitHub Actions workflows were removed from `PureCipher/xsecuremcp2.0`
on 2026-09-07 at the maintainer's request. There is no automated sync, CI,
publishing, documentation deployment, issue triage, or PR moderation.

FastMCP updates will be taken manually from upstream releases/tags, rather
than continuously merging upstream `main`. No changes are pushed to
`PrefectHQ/fastmcp`. Choosing or importing the next release is a separate task.

## Workflow review

Each of the following workflows was reviewed and removed:

| Workflow file | Previous purpose |
| --- | --- |
| `auto-close-duplicates.yml` | Close duplicate issues using the Marvin App. |
| `auto-close-needs-mre.yml` | Close inactive issues awaiting reproductions. |
| `deploy-docs.yml` | Deploy the upstream Mintlify documentation project. |
| `marvin-comment-on-issue.yml` | Run the `/marvin` issue assistant. |
| `marvin-comment-on-pr.yml` | Run the `/marvin` PR assistant. |
| `marvin-dedupe-issues.yml` | Find and label duplicate issues with AI. |
| `marvin-label-triage.yml` | Apply upstream labels and contributor policy. |
| `marvin-test-failure.yml` | Generate AI comments about failed CI runs. |
| `marvin-triage-issue.yml` | Triage issues for named upstream maintainers. |
| `minimize-resolved-reviews.yml` | Hide resolved PR review comments. |
| `publish-fastmcp-slim.yml` | Publish upstream `fastmcp-slim` to PyPI. |
| `publish-fastmcp.yml` | Publish upstream `fastmcp` and prepare documentation publication. |
| `publish-fastmcp-remote.yml` | Publish upstream `fastmcp-remote` to PyPI. |
| `publish-fastmcp-tasks.yml` | Publish upstream `fastmcp-tasks` to PyPI. |
| `require-issue-link.yml` | Close/reopen external PRs using upstream assignment rules. |
| `run-schema-crash-test.yml` | Test against an external corpus of 232K schemas. |
| `run-static.yml` | Run formatting, lint, typing, and repository checks. |
| `run-tests.yml` | Run the Python/OS test matrix, integration/conformance tests, and package smoke checks. |
| `run-upgrade-checks.yml` | Test upgraded dependencies and create/close failure issues. |
| `sync.yml` | Merge upstream `main` into this fork daily and push. |
| `update-config-schema.yml` | Open generated-schema PRs as Marvin. |
| `update-sdk-docs.yml` | Open generated SDK-documentation PRs as Marvin. |

The three composite actions (`run-claude`, `run-pytest`, and `setup-uv`) are
also removed because no workflows use them. Helper scripts, generated docs,
and application code remain intact. Historical Actions runs are not deleted.

## Manual validation

Tests and checks remain available locally:

```sh
uv sync
uv run pytest -n auto
uv run prek run --all-files
```

Run them before committing an upstream release update. Removing automation
does not resolve the existing Windows/minimum-dependency test failures or
replace local validation. Inherited upstream contributor/release instructions
may describe bots and publishing procedures that are not enabled in this fork.

Future release imports may contain `.github/workflows` or `.github/actions`.
Review and exclude those definitions to keep automation disabled.
