import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadEnv } from 'vite';
import { loadComponent } from './componentHarness.ts';

for (const [label, value, expected] of [
  ['empty', '', 'http://127.0.0.1:8000'],
  ['blank', '   ', 'http://127.0.0.1:8000'],
  ['configured', ' https://backend.example.test:8443 ', 'https://backend.example.test:8443'],
]) {
  test(`Vite proxy handles ${label} environment configuration through loadEnv`, (t) => {
    const original = process.env.VITE_API_PROXY_TARGET;
    process.env.VITE_API_PROXY_TARGET = value;
    t.after(() => {
      if (original === undefined) delete process.env.VITE_API_PROXY_TARGET;
      else process.env.VITE_API_PROXY_TARGET = original;
    });
    const calls: unknown[][] = [];
    const config = loadComponent('../../frontend/vite.config.ts', {
      vite: {
        defineConfig: (callback: unknown) => callback,
        loadEnv: (mode: string, directory: string, prefix: string) => {
          calls.push([mode, directory, prefix]);
          return loadEnv(mode, directory, prefix);
        },
      },
      '@vitejs/plugin-react': () => 'react-plugin',
    }).default({ mode: 'production' });
    assert.deepEqual(calls, [['production', process.cwd(), 'VITE_']]);
    assert.equal(config.server.proxy['/api'].target, expected);
    assert.equal(config.server.host, '0.0.0.0');
    assert.equal(config.server.port, 5173);
    assert.equal(config.server.proxy['/api'].changeOrigin, true);
  });
}
