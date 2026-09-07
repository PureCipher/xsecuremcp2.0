const test = require('node:test');
const assert = require('node:assert/strict');
const { check, pendingReleases, marker } = require('./check-upstream-releases.cjs');

const release = (id, extra = {}) => ({
  id, tag_name: `v4.0.${id}`, draft: false, prerelease: false,
  published_at: `2026-09-${String(id).padStart(2, '0')}T12:00:00Z`, ...extra,
});

test('finds every new stable release, in publication order, including maintenance releases', () => {
  assert.deepEqual(pendingReleases([
    release(8), release(7, { tag_name: 'v3.5.1' }), release(1),
    release(9, { prerelease: true }), release(10, { draft: true }),
  ], []).map(r => r.id), [7, 8]);
});

test('both open and closed alerts suppress repeats; pull requests do not', () => {
  assert.deepEqual(pendingReleases([release(7), release(8), release(9)], [
    { body: marker(release(7)), state: 'closed' },
    { body: marker(release(8)), state: 'open' },
    { body: marker(release(9)), pull_request: {} },
  ]).map(r => r.id), [9]);
});

function harness() {
  const created = [];
  const listReleases = Symbol('releases');
  const listForRepo = Symbol('issues');
  return {
    created,
    context: { repo: { owner: 'PureCipher', repo: 'xsecuremcp2.0' }, ref: 'refs/heads/main' },
    core: { info() {}, summary: { addRaw() { return this; }, async write() {} } },
    assignee: 'svkrishna',
    github: {
      paginate: async (method) => method === listReleases ? [release(7)] : [],
      rest: { repos: { listReleases }, issues: { listForRepo, create: async issue => created.push(issue) } },
    },
  };
}

test('notification targets only the fork and the selected assignee', async () => {
  const args = harness();
  assert.equal(await check(args), 1);
  assert.equal(args.created.length, 1);
  assert.equal(args.created[0].owner, 'PureCipher');
  assert.deepEqual(args.created[0].assignees, ['svkrishna']);
  assert.match(args.created[0].body, /https:\/\/github.com\/PrefectHQ\/fastmcp\/releases\/tag\/v4.0.7/);
});

test('dry run makes no notification writes', async () => {
  const args = harness();
  assert.equal(await check({ ...args, dryRun: true }), 1);
  assert.equal(args.created.length, 0);
});

test('upstream and non-main execution are rejected before any API call', async () => {
  for (const context of [
    { repo: { owner: 'PrefectHQ', repo: 'fastmcp' }, ref: 'refs/heads/main' },
    { repo: { owner: 'PureCipher', repo: 'xsecuremcp2.0' }, ref: 'refs/heads/other' },
  ]) {
    await assert.rejects(check({ context }), /restricted/);
  }
});
