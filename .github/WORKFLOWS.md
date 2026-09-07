# Python and Docker builds

This repository has one workflow: `build-packages.yml`. Every push to `main`
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
remain removed. Future imports from upstream release tags should retain this
single fork-specific workflow rather than restore upstream automation.
