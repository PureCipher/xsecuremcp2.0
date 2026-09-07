const fs = require('node:fs');
const path = require('node:path');

const REPO = 'PureCipher/xsecuremcp2.0';
const TAG = 'build-latest';
const MARKER = '<!-- purecipher-rolling-build -->';

function oldImageVersions(versions, currentDigest) {
  if (!/^sha256:[a-f0-9]{64}$/.test(currentDigest)) {
    throw new Error('Refusing cleanup without a valid current image digest');
  }
  const current = versions.find(v => v.name === currentDigest);
  if (!current || !current.metadata?.container?.tags?.includes('latest')) {
    throw new Error('Refusing cleanup: the new latest image is not visible in GHCR');
  }
  // The workflow pushes a single-platform Docker manifest, without attestations.
  // Preserve tagged versions, including any manually maintained image tags.
  return versions.filter(v => v.name !== currentDigest && v.metadata?.container?.tags?.length === 0);
}

function managedAsset(name) {
  return /^(fastmcp(?:[_-](?:slim|remote|tasks))?)-.*\.(whl|tar\.gz)$/.test(name)
    || ['constraints.txt', 'requirements.txt', 'build.json', 'SHA256SUMS', 'xsecuremcp2.0-python.zip'].includes(name);
}

async function publish({ github, context, core }) {
  if (`${context.repo.owner}/${context.repo.repo}` !== REPO || context.ref !== 'refs/heads/main') {
    throw new Error('Publishing is restricted to PureCipher/xsecuremcp2.0 main');
  }
  const dist = path.resolve('dist');
  const build = JSON.parse(fs.readFileSync(path.join(dist, 'build.json'), 'utf8'));
  if (build.repository !== REPO || build.commit !== context.sha) {
    throw new Error('Build metadata does not match the checked-out commit');
  }
  const { data: main } = await github.rest.git.getRef({ ...context.repo, ref: 'heads/main' });
  if (main.object.sha !== context.sha) {
    throw new Error('Main changed during the build; a newer run will publish it');
  }

  let release;
  try {
    ({ data: release } = await github.rest.repos.getReleaseByTag({ ...context.repo, tag: TAG }));
    if (!release.body?.includes(MARKER)) throw new Error('The build-latest release is not owned by this workflow');
    if (release.immutable) throw new Error('The build-latest release must remain mutable');
  } catch (error) {
    if (error.status !== 404) throw error;
    ({ data: release } = await github.rest.repos.createRelease({
      ...context.repo, tag_name: TAG, target_commitish: context.sha,
      name: 'Latest main build', body: MARKER, draft: true, prerelease: true,
    }));
  }

  const existing = await github.paginate(github.rest.repos.listReleaseAssets, {
    ...context.repo, release_id: release.id, per_page: 100,
  });
  const names = fs.readdirSync(dist).filter(managedAsset);
  // Upload versioned wheels first; requirements.txt changes only after they exist.
  names.sort((a, b) => Number(a === 'requirements.txt') - Number(b === 'requirements.txt'));
  for (const name of names) {
    const previous = existing.find(asset => asset.name === name);
    const temporaryName = previous ? `upload-${context.runId}-${name}` : name;
    const leftover = existing.find(asset => asset.name === temporaryName && asset.name !== name);
    if (leftover) await github.rest.repos.deleteReleaseAsset({ ...context.repo, asset_id: leftover.id });
    const data = fs.readFileSync(path.join(dist, name));
    const { data: uploaded } = await github.rest.repos.uploadReleaseAsset({
      ...context.repo, release_id: release.id, name: temporaryName, data,
      headers: { 'content-type': 'application/octet-stream', 'content-length': data.length },
    });
    if (previous) {
      await github.rest.repos.deleteReleaseAsset({ ...context.repo, asset_id: previous.id });
      await github.rest.repos.updateReleaseAsset({ ...context.repo, asset_id: uploaded.id, name });
    }
  }

  // Move only our rolling build tag. Upstream version tags are never modified.
  try {
    await github.rest.git.updateRef({ ...context.repo, ref: `tags/${TAG}`, sha: context.sha, force: true });
  } catch (error) {
    if (error.status !== 404 && error.status !== 422) throw error;
    await github.rest.git.createRef({ ...context.repo, ref: `refs/tags/${TAG}`, sha: context.sha });
  }
  const body = `${MARKER}\nBuilt from [${context.sha.slice(0, 12)}](https://github.com/${REPO}/commit/${context.sha}).\n\n`
    + `Python package version: \`${build.version}\`. Docker: \`ghcr.io/purecipher/xsecuremcp2.0:latest\` (linux/amd64).\n\n`
    + 'Install the four matching fork wheels with:\n\n```sh\n'
    + `python -m pip install --upgrade -r https://github.com/${REPO}/releases/download/${TAG}/requirements.txt\n`
    + '```\n\nThis rolling build replaces previous build assets after successful tests. It is not an upstream FastMCP release.';
  await github.rest.repos.updateRelease({
    ...context.repo, release_id: release.id, name: 'Latest main build',
    body, draft: false, prerelease: true, make_latest: 'false',
  });
  for (const asset of existing) {
    if (managedAsset(asset.name) && !names.includes(asset.name)) {
      await github.rest.repos.deleteReleaseAsset({ ...context.repo, asset_id: asset.id });
    }
  }
  await core.summary.addLink('Download Python packages', `https://github.com/${REPO}/releases/tag/${TAG}`).write();
}

async function cleanupImage({ github, context }) {
  if (`${context.repo.owner}/${context.repo.repo}` !== REPO || context.ref !== 'refs/heads/main') {
    throw new Error('Image cleanup is restricted to the PureCipher fork main branch');
  }
  const packageArgs = { org: 'PureCipher', package_type: 'container', package_name: 'xsecuremcp2.0' };
  const versions = await github.paginate(github.rest.packages.getAllPackageVersionsForPackageOwnedByOrg, {
    ...packageArgs, per_page: 100,
  });
  for (const version of oldImageVersions(versions, process.env.IMAGE_DIGEST || '')) {
    await github.rest.packages.deletePackageVersionForOrg({ ...packageArgs, package_version_id: version.id });
  }
}

module.exports = { publish, cleanupImage, oldImageVersions, managedAsset };
