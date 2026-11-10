import assert from 'node:assert/strict';
import { test } from 'node:test';
import { translations } from '../src/utils/i18n.ts';
import { PAYMENT_METHOD_LABELS, RECEIPT_METHODS, SUPPLIER_PAYMENT_METHODS, paymentMethodLabel } from '../src/utils/paymentMethods.ts';
import { loadComponent } from './componentHarness.ts';

test('payment method codes map to translated labels and legacy free text passes through', () => {
  assert.equal(paymentMethodLabel('CARD_TO_CARD'), 'کارت‌به‌کارت / حواله پایا');
  assert.equal(paymentMethodLabel('کارتخوان / نقدی'), 'کارتخوان / نقدی');
  assert.equal(paymentMethodLabel(''), '-');
  for (const label of Object.values(PAYMENT_METHOD_LABELS)) assert.ok(translations[label]?.en, label);
  for (const code of [...RECEIPT_METHODS, ...SUPPLIER_PAYMENT_METHODS]) assert.ok(PAYMENT_METHOD_LABELS[code]);
});

test('vendor chunking keeps icon packages out of the React core chunk', () => {
  const config = loadComponent('../../frontend/vite.config.ts', {
    vite: { defineConfig: (callback: unknown) => callback, loadEnv: () => ({}) },
    '@vitejs/plugin-react': () => 'react-plugin',
  }).default({ mode: 'production' });
  const chunk = config.build.rollupOptions.output.manualChunks;
  assert.equal(chunk('/app/node_modules/react/index.js'), 'react-core');
  assert.equal(chunk('/app/node_modules/react-dom/client.js'), 'react-core');
  assert.equal(chunk('/app/node_modules/react-router/dist/index.js'), 'react-router');
  assert.equal(chunk('/app/node_modules/lucide-react/dist/esm/icons/x.js'), undefined);
  assert.equal(chunk('/app/node_modules/axios/index.js'), 'axios');
});
