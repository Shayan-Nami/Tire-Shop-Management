import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createRequestSequence, fetchAllPages, isCurrentInvoiceVehicle, invoiceSubmitLabel } from '../src/utils/invoiceRequests.ts';
import { deferred, page } from './componentHarness.ts';

test('selectors fetch more than 100 records, including a server-capped page size', async () => {
  const calls: number[] = [];
  const results = await fetchAllPages(async (number) => {
    calls.push(number);
    return page(Array.from({ length: 25 }, (_, index) => (number - 1) * 25 + index), number, 6);
  });
  assert.equal(results.length, 150);
  assert.equal(results.at(-1), 149);
  assert.deepEqual(calls, [1, 2, 3, 4, 5, 6]);
});

test('pagination honors next even without total_pages and rejects malformed progress', async () => {
  const results = await fetchAllPages(async (number) => ({ ...page([number], number), total_pages: undefined!, next: number === 1 ? '?page=2' : null }));
  assert.deepEqual(results, [1, 2]);
  await assert.rejects(fetchAllPages(async () => page([], 1, 2)), /صفحه‌بندی/);
  await assert.rejects(fetchAllPages(async () => page([1], 1, 2)), /صفحه‌بندی/);
});

test('pagination stops after supersession and does not return partial stale data', async () => {
  const requests = createRequestSequence();
  const request = requests.begin();
  const pending = deferred<ReturnType<typeof page<number>>>();
  let calls = 0;
  const result = fetchAllPages(() => { calls++; return pending.promise; }, () => requests.isCurrent(request));
  requests.invalidate();
  pending.resolve(page([1], 1, 4));
  assert.deepEqual(await result, []);
  assert.equal(calls, 1);
});

test('later-page failure propagates instead of silently truncating selectors', async () => {
  await assert.rejects(fetchAllPages(async (number) => {
    if (number === 2) throw new Error('offline');
    return page([1], number, 2);
  }), /offline/);
});

test('submission requires a loaded vehicle owned by the current customer', () => {
  const vehicle = { vehicle_id: 3, customer: 2, model: 'car', license_plate: '12ب345-ایران11' };
  assert.equal(isCurrentInvoiceVehicle(2, 3, [vehicle], false), true);
  assert.equal(isCurrentInvoiceVehicle(1, 3, [vehicle], false), false);
  assert.equal(isCurrentInvoiceVehicle(2, 3, [vehicle], true), false);
  assert.equal(isCurrentInvoiceVehicle(2, 3, [], false), false);
  assert.equal(isCurrentInvoiceVehicle('', 3, [vehicle], false), false);
});

test('draft and confirmed actions use distinct pending and idle wording', () => {
  assert.match(invoiceSubmitLabel('DRAFT', false), /ذخیره پیش‌نویس/);
  assert.match(invoiceSubmitLabel('DRAFT', true), /در حال ذخیره پیش‌نویس/);
  assert.match(invoiceSubmitLabel('CONFIRMED', false), /نهایی‌سازی/);
  assert.match(invoiceSubmitLabel('CONFIRMED', true), /در حال صدور/);
});
