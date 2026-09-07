# Python and Docker builds

The build workflow is `build-packages.yml`. Every push to `main`
(and a manual run on `main`) tests and publishes the PureCipher fork. It never
pushes source code or packages to PrefectHQ/FastMCP or PyPI. Upstream release/tag
imports remain manual.

## Validation and publication

1. Install locked dependencies and run the complete test suite. Unit tests run
   with two workers; integration, subprocess, and conformance tests run serially.
   Tests requiring unavailable external credentials retain their existing skips.
2. Run formatting, lint, typing, and publication-safety tests.
3. Build the four matching Python workspace packages and export locked runtime
   constraints. Verify them in a fresh installation, including an MCP tool call,
   CLI entry points, and database migrations.
4. Build a Linux AMD64 Docker image and verify the installed packages, launchers,
   and `/registry/health` endpoint before pushing it.
5. Publish `ghcr.io/purecipher/xsecuremcp2.0:latest` and the `build-latest`
   GitHub Release. Remove superseded release assets and untagged image versions
   only after the new outputs have passed validation and been published.

A failed test/build does not replace the previous outputs. Publication is
serialized, and a build whose commit is no longer `main` stops before publishing.
Python uploads and Docker pushes are separate services, so an upload or cleanup
failure can leave a partially updated publication; the workflow reports failure
and can be rerun. No upstream version tags or unrelated releases are deleted.
The rolling `build-latest` tag is the only Git tag this workflow updates.

## Hugging Face Space

After the GitHub publications succeed, the build workflow uploads the tested
four wheels and locked constraints to
[purecipher/xsecuremcp](https://huggingface.co/spaces/purecipher/xsecuremcp).
The Space README selects the Docker SDK and port 8000. Its Dockerfile installs
the tested wheels and runs as user 1000; CI checks this container's MCP calls,
database migrations, and registry health before uploading it. Hugging Face
then builds and starts the Space asynchronously.
The Space opens `/registry/health`; it hosts the backend API, while the separate
registry console is deployed independently. The package's legacy UI stays disabled.
Edit `.github/huggingface/README.md` to update the Space page. The build script
fills its commit and package-version placeholders during publication, so the
page stays consistent with the installed wheels.

The GitHub Actions secret `HF_TOKEN` must have write access to this Space.
Configure `PURECIPHER_SIGNING_SECRET` in the Space secrets before startup, and
`DATABASE_URL` for persistent PostgreSQL storage if needed. Existing Space
secrets and visibility are preserved. The deployment replaces its Dockerfile,
README, `.dockerignore`, license, build metadata, and `wheels/` artifacts;
unrelated existing source files are retained but excluded from the Docker build.
Superseded wheels are removed from the current Space revision. Hub Git history
is retained. No model or dataset repository is created.

## Install with pip

GitHub Packages does not provide a native Python/pip registry. The rolling
GitHub Release hosts wheel files, source distributions, a ZIP bundle, locked
constraints, and checksums instead:

```sh
python -m pip install --upgrade -r https://github.com/PureCipher/xsecuremcp2.0/releases/download/build-latest/requirements.txt
```

The existing distribution names (`fastmcp`, `fastmcp-slim`, `fastmcp-remote`, and
`fastmcp-tasks`) are retained for compatibility. The requirements file points to
all four matching **fork wheels** on GitHub, so pip does not substitute upstream
FastMCP wheels. Third-party runtime dependencies come from PyPI at the tested
locked versions.

Alternatively, download `xsecuremcp2.0-python.zip` from the
[rolling build release](https://github.com/PureCipher/xsecuremcp2.0/releases/tag/build-latest),
extract it into an empty directory, then run:

```sh
python -m pip install --constraint constraints.txt ./*.whl
```

`SHA256SUMS` and `build.json` identify the files, package version, and source
commit. The rolling release is marked as a prerelease, not an upstream release.

## Run Docker

```sh
docker pull ghcr.io/purecipher/xsecuremcp2.0:latest
docker run --rm -p 8000:8000 \
  -e PURECIPHER_SIGNING_SECRET="$PURECIPHER_SIGNING_SECRET" \
  -e DATABASE_URL="$DATABASE_URL" \
  ghcr.io/purecipher/xsecuremcp2.0:latest
```

Set a signing secret before running. `DATABASE_URL` points to PostgreSQL for
persistent storage; omitting it uses ephemeral storage. The image contains
Node/npm, uv/uvx, and the Docker CLI for package introspection. A Docker daemon
is not included. The existing Compose file remains available for local source
builds and PostgreSQL setup.

GHCR packages are private by default even for public source repositories. If
the image is private, authenticate with `docker login ghcr.io` using a GitHub
personal access token with `read:packages`, or change the package visibility in
GitHub if public anonymous pulls are wanted.

## Permissions and retention

GitHub Actions must be enabled for this repository. The workflow uses its
built-in `GITHUB_TOKEN` with `contents: write` for the rolling release and
`packages: write` for GHCR. No PyPI token, Docker Hub credentials, or upstream
repository write access is needed. The publishing repository must have admin
access to its GHCR package to delete older versions; this is assigned
implicitly when the workflow creates the package. Manually tagged image
versions are preserved. Historical workflow logs are not build packages and
are left to GitHub's normal retention policy.

All previous sync, publishing, documentation, and maintainer-bot workflows
remain removed. Future imports from upstream release tags should retain these
fork-specific workflows rather than restore upstream automation.

## Upstream release email notifications

`check-upstream-releases.yml` checks `PrefectHQ/fastmcp` daily at 03:17 UTC
(08:47 India time). For each newly published **stable release**, it creates one
issue here assigned to `svkrishna`, with a link to the upstream release notes
and a reminder to review and merge the release tag into `main` manually.
It never merges, changes source code, or writes upstream. Prereleases, draft
releases, and bare tags without a published release are ignored. The starting
baseline is `v4.0.3`, published September 5, 2026; historical releases do not
generate alerts. New maintenance releases are included even if a higher major
version already exists.

GitHub delivers assignment emails according to the recipient's
[notification settings](https://github.com/settings/notifications). Enable
**Email** for participating notifications and ensure this repository is not
ignored. No SMTP password is required. The workflow cannot verify inbox
delivery or override personal email preferences. To change the recipient, set
the repository Actions variable `FASTMCP_RELEASE_ASSIGNEE` to an assignable
GitHub username.

Both open and closed alert issues prevent duplicate notifications; keep their
hidden release marker intact. Deleting an alert issue allows it to be recreated.
A manual run defaults to a dry run; clear `dry_run` to send pending alerts.
When no new release exists, no issue or email is generated. The workflow has
only source read and fork issue write permissions. GitHub may delay scheduled
runs and disables schedules in public repositories after 60 days without
repository activity; re-enable this workflow in Actions if that occurs.
