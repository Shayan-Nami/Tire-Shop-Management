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

test('Vite manualChunks isolates React runtime from lucide-react on POSIX and Windows paths', () => {
  const config = loadComponent('../../frontend/vite.config.ts', {
    vite: {
      defineConfig: (callback: unknown) => callback,
      loadEnv: () => ({}),
    },
    '@vitejs/plugin-react': () => 'react-plugin',
  }).default({ mode: 'production' });

  const manualChunks = config.build.rollupOptions.output.manualChunks as (id: string) => string | undefined;
  assert.equal(manualChunks('/repo/frontend/node_modules/react/index.js'), 'react-core');
  assert.equal(manualChunks('C:\\repo\\frontend\\node_modules\\react\\jsx-runtime.js'), 'react-core');
  assert.equal(manualChunks('C:\\repo\\frontend\\node_modules\\react-dom\\client.js'), 'react-core');
  assert.equal(manualChunks('/repo/frontend/node_modules/scheduler/index.js'), 'react-core');
  assert.equal(manualChunks('/repo/frontend/node_modules/react-router-dom/dist/index.js'), 'react-router');
  assert.equal(manualChunks('C:\\repo\\frontend\\node_modules\\axios\\lib\\axios.js'), 'axios');
  assert.equal(manualChunks('/repo/frontend/node_modules/lucide-react/dist/esm/lucide-react.js'), undefined);
  assert.equal(manualChunks('C:\\repo\\frontend\\node_modules\\lucide-react\\dist\\esm\\icons\\x.js'), undefined);
});
