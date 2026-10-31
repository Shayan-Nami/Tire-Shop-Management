import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fetchAllPages } from '../src/utils/invoiceRequests.ts';
import { loadComponent, page } from './componentHarness.ts';

function loadApi(path: string, get: (url: string, config?: any) => Promise<any>) {
  const client = { apiClient: { get } };
  // The API modules and pagination adapter both use the same controlled transport.
  const pagination = loadComponent('../src/api/pagination.ts', {
    './client': client,
    '../utils/invoiceRequests': { fetchAllPages },
  });
  return loadComponent(path, { './client': client, './pagination': pagination });
}

for (const [module, api, method, endpoint] of [
  ['auth', 'authApi', 'getUsers', '/auth/users/'],
  ['catalog', 'catalogApi', 'getBrands', '/catalog/brands/'],
  ['catalog', 'catalogApi', 'getSizes', '/catalog/sizes/'],
  ['catalog', 'catalogApi', 'getLowStockTires', '/catalog/tires/low-stock/'],
]) {
  test(`${method} returns every backend page, not only the first batch`, async () => {
    const calls: any[] = [];
    const records = Array.from({ length: 205 }, (_, id) => ({ id: id + 1 }));
    const get = async (url: string, config?: any) => {
      calls.push({ url, params: config?.params });
      const current = config?.params?.page ?? 1;
      const batch = page(records.slice((current - 1) * 100, current * 100), current, 3);
      return { data: { ...batch, count: records.length } };
    };
    const result = await loadApi(`../src/api/${module}.ts`, get)[api][method]();
    assert.deepEqual(result, records);
    assert.deepEqual(calls, [1, 2, 3].map((current) => ({ url: endpoint, params: { page: current, page_size: 100 } })));
  });
}

test('collection APIs retain compatibility with unpaginated arrays', async () => {
  const records = [{ brand_id: 1, brand_name: 'Brand' }];
  let calls = 0;
  const { catalogApi } = loadApi('../src/api/catalog.ts', async () => { calls++; return { data: records }; });
  assert.deepEqual(await catalogApi.getBrands(), records);
  assert.equal(calls, 1);
});

test('collection APIs reject failed later pages instead of silently returning incomplete options', async () => {
  const { catalogApi } = loadApi('../src/api/catalog.ts', async (_url, config) => {
    if (config?.params?.page === 2) throw new Error('Page two unavailable');
    return { data: page([{ size_id: 1 }], 1, 2) };
  });
  await assert.rejects(catalogApi.getSizes(), /Page two unavailable/);
});

test('collection APIs reject a repeated page rather than looping or duplicating records', async () => {
  const { authApi } = loadApi('../src/api/auth.ts', async () => ({ data: page([{ id: 1 }], 1, 2) }));
  await assert.rejects(authApi.getUsers(), /صفحه/);
});
