import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';

test('backend contract verifier rejects a response missing required UI fields', () => {
  const result = spawnSync(process.execPath, ['tests/checkBackendContracts.mjs'], {
    cwd: new URL('..', import.meta.url), encoding: 'utf8',
    input: JSON.stringify([{ type: 'DashboardStats', data: {} }]),
  });
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stderr, /missing the following properties/);
});
