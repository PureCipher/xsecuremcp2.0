const assert = require('node:assert/strict');
const test = require('node:test');
const { oldImageVersions, managedAsset, publish, cleanupImage } = require('./publish-build.cjs');

const current = `sha256:${'a'.repeat(64)}`;
const older = `sha256:${'b'.repeat(64)}`;
const version = (id, name, tags) => ({ id, name, metadata: { container: { tags } } });

test('cleanup retains latest and all manually tagged versions', () => {
  const versions = [version(1, current, ['latest']), version(2, older, []), version(3, 'manual', ['stable'])];
  assert.deepEqual(oldImageVersions(versions, current).map(v => v.id), [2]);
});

test('cleanup refuses to delete when latest is missing or digest is invalid', () => {
  assert.throws(() => oldImageVersions([version(1, current, [])], current));
  assert.throws(() => oldImageVersions([version(1, older, ['latest'])], current));
  assert.throws(() => oldImageVersions([], ''));
});

test('cleanup preserves versions with missing metadata instead of guessing', () => {
  assert.deepEqual(oldImageVersions([version(1, current, ['latest']), { id: 2 }], current), []);
});

test('release cleanup only selects owned asset names', () => {
  assert.equal(managedAsset('fastmcp_slim-4.0.1.dev1+abc-py3-none-any.whl'), true);
  assert.equal(managedAsset('fastmcp-4.0.1.tar.gz'), true);
  assert.equal(managedAsset('xsecuremcp2.0-python.zip'), true);
  assert.equal(managedAsset('customer-backup.zip'), false);
  assert.equal(managedAsset('other-package-1.0.whl'), false);
});

test('publication and deletion reject upstream and non-main refs before API calls', async () => {
  for (const operation of [publish, cleanupImage]) {
    await assert.rejects(operation({ context: { repo: { owner: 'PrefectHQ', repo: 'fastmcp' }, ref: 'refs/heads/main' } }));
    await assert.rejects(operation({ context: { repo: { owner: 'PureCipher', repo: 'xsecuremcp2.0' }, ref: 'refs/heads/feature' } }));
  }
});
