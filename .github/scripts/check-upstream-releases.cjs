const REPO = 'PureCipher/xsecuremcp2.0';
const UPSTREAM = { owner: 'PrefectHQ', repo: 'fastmcp' };
// Start after the current stable release; do not alert on historical releases.
const BASELINE = '2026-09-05T00:30:56Z';

function marker(release) {
  return `<!-- fastmcp-release-alert:${release.id} -->`;
}

function pendingReleases(releases, issues) {
  const seen = new Set(issues.filter(issue => !issue.pull_request)
    .flatMap(issue => issue.body?.match(/<!-- fastmcp-release-alert:\d+ -->/g) || []));
  return releases.filter(release => !release.draft && !release.prerelease
    && Date.parse(release.published_at) > Date.parse(BASELINE)
    && !seen.has(marker(release)))
    .sort((a, b) => Date.parse(a.published_at) - Date.parse(b.published_at));
}

async function check({ github, context, core, assignee, dryRun = false }) {
  if (`${context.repo.owner}/${context.repo.repo}` !== REPO || context.ref !== 'refs/heads/main') {
    throw new Error('Release alerts are restricted to PureCipher/xsecuremcp2.0 main');
  }
  if (!/^[a-zA-Z0-9][a-zA-Z0-9-]{0,38}$/.test(assignee || '')) {
    throw new Error('A valid GitHub notification assignee is required');
  }
  const releases = await github.paginate(github.rest.repos.listReleases, { ...UPSTREAM, per_page: 100 });
  // Include closed issues so closing an alert never causes another notification.
  const issues = await github.paginate(github.rest.issues.listForRepo, {
    ...context.repo, state: 'all', creator: 'github-actions[bot]', per_page: 100,
  });
  const pending = pendingReleases(releases, issues);
  for (const release of pending) {
    const url = `https://github.com/PrefectHQ/fastmcp/releases/tag/${encodeURIComponent(release.tag_name)}`;
    const body = `${marker(release)}\nA new stable FastMCP release is available: [${release.tag_name}](${url}).\n\n`
      + `Published: ${release.published_at}.\n\n`
      + 'Review the release notes, then manually import the release tag into PureCipher/xsecuremcp2.0 main and run the tests before pushing.\n\n'
      + 'This workflow only notifies you; it does not merge changes, move tags, or write to the upstream repository. Close this issue after review.';
    if (dryRun) {
      core.info(`Would notify ${assignee} about ${release.tag_name}`);
    } else {
      await github.rest.issues.create({
        ...context.repo, title: `FastMCP ${release.tag_name}: review for manual merge`,
        body, assignees: [assignee],
      });
    }
  }
  await core.summary.addRaw(`${dryRun ? 'Dry run: ' : ''}${pending.length} new stable FastMCP release(s).`).write();
  return pending.length;
}

module.exports = { check, pendingReleases, marker };
