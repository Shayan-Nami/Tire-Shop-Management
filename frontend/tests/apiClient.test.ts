import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';
import * as storageModule from '../src/utils/storage.ts';
import { deferred, loadComponent } from './componentHarness.ts';

function response(config: InternalAxiosRequestConfig, data: any = {}, status = 200) {
  return { config, data, status, statusText: String(status), headers: {} };
}
function rejectRequest(config: InternalAxiosRequestConfig, status = 401) {
  return Promise.reject(new AxiosError('Request rejected', 'ERR_BAD_REQUEST', config, undefined, response(config, {}, status)));
}
function setup(t: TestContext, adapter: AxiosAdapter, refresh: (url: string, data: any) => Promise<any>, env: Record<string, string> = {}) {
  const values = new Map([['access_token', 'old-access'], ['refresh_token', 'old-refresh'], ['user_info', '{}']]);
  const location = { href: '/dashboard' };
  const descriptors = ['localStorage', 'window'].map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)] as const);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  } });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { location } });
  t.after(() => {
    for (const [key, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  });
  const { apiClient, API_BASE_URL } = loadComponent('../src/api/client.ts', {
    axios: { create: (config: any) => axios.create({ ...config, adapter }), post: refresh },
    '../utils/storage': storageModule,
  }, env);
  return { apiClient, API_BASE_URL, values, location };
}

for (const [label, env, expected] of [
  ['missing', {}, '/api/v1'],
  ['empty', { VITE_API_BASE_URL: '' }, '/api/v1'],
  ['blank', { VITE_API_BASE_URL: '  ' }, '/api/v1'],
  ['relative', { VITE_API_BASE_URL: ' /gateway/api/v1/ ' }, '/gateway/api/v1'],
  ['absolute', { VITE_API_BASE_URL: ' https://api.example.test/api/v1/// ' }, 'https://api.example.test/api/v1'],
] as const) {
  test(`API base handles ${label} environment configuration`, async (t) => {
    const { apiClient, API_BASE_URL } = setup(t, async (config) => response(config), async () => ({}), env);
    assert.equal(API_BASE_URL, expected);
    assert.equal(apiClient.defaults.baseURL, expected);
  });
}

test('configured API base is used for both ordinary requests and token refresh', async (t) => {
  const refreshes: string[] = [];
  const { apiClient } = setup(t, async (config) => {
    assert.equal(config.baseURL, 'https://api.example.test/api/v1');
    if (config.headers.Authorization === 'Bearer old-access') return rejectRequest(config);
    return response(config);
  }, async (url) => {
    refreshes.push(url);
    return { data: { access: 'new-access', refresh: 'new-refresh' } };
  }, { VITE_API_BASE_URL: 'https://api.example.test/api/v1/' });
  await apiClient.get('/auth/profile/');
  assert.deepEqual(refreshes, ['https://api.example.test/api/v1/auth/token/refresh/']);
});

test('concurrent 401s share one refresh and replay with the rotated access token', async (t) => {
  const pending = deferred<any>();
  const attempts: any[] = [];
  const refreshes: any[] = [];
  const { apiClient, values } = setup(t, async (config) => {
    attempts.push({ url: config.url, token: config.headers.Authorization });
    if (config.headers.Authorization === 'Bearer old-access') return rejectRequest(config);
    return response(config);
  }, async (url, data) => { refreshes.push({ url, data }); return pending.promise; });
  const requests = [apiClient.get('/auth/profile/'), apiClient.get('/catalog/tires/')];
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.deepEqual(refreshes, [{ url: '/api/v1/auth/token/refresh/', data: { refresh: 'old-refresh' } }]);
  pending.resolve({ data: { access: 'new-access', refresh: 'new-refresh' } });
  await Promise.all(requests);
  assert.equal(attempts.length, 4);
  assert.equal(attempts.filter((attempt) => attempt.token === 'Bearer new-access').length, 2);
  assert.equal(values.get('access_token'), 'new-access');
  assert.equal(values.get('refresh_token'), 'new-refresh');
});

test('refresh rejection rejects queued requests and clears the local session', async (t) => {
  const pending = deferred<any>();
  const { apiClient, values, location } = setup(t, rejectRequest, () => pending.promise);
  const requests = Promise.allSettled([apiClient.get('/auth/profile/'), apiClient.get('/catalog/tires/')]);
  await new Promise<void>((resolve) => setImmediate(resolve));
  pending.reject(new AxiosError('Refresh revoked', 'ERR_BAD_REQUEST', undefined, undefined, { status: 401, data: {}, statusText: '401', headers: {}, config: {} as InternalAxiosRequestConfig }));
  assert.deepEqual((await requests).map((result) => result.status), ['rejected', 'rejected']);
  assert.equal(values.size, 0);
  assert.equal(location.href, '/login');
});

test('invalid login credentials never trigger refresh', async (t) => {
  let refreshes = 0;
  const { apiClient, values } = setup(t, rejectRequest, async () => { refreshes++; return {}; });
  await assert.rejects(apiClient.post('/auth/login/', { username: 'manager', password: 'incorrect' }));
  assert.equal(refreshes, 0);
  assert.equal(values.get('refresh_token'), 'old-refresh');
});

test('missing refresh token clears the session without a refresh request', async (t) => {
  let refreshes = 0;
  const { apiClient, values, location } = setup(t, rejectRequest, async () => { refreshes++; return {}; });
  values.delete('refresh_token');
  await assert.rejects(apiClient.get('/auth/profile/'));
  assert.equal(refreshes, 0);
  assert.equal(values.size, 0);
  assert.equal(location.href, '/login');
});

test('queued requests that still receive 401 are retried at most once', async (t) => {
  const pending = deferred<any>();
  let refreshes = 0;
  let attempts = 0;
  const { apiClient } = setup(t, async (config) => { attempts++; return rejectRequest(config); }, async () => {
    refreshes++;
    return pending.promise;
  });
  const requests = Promise.allSettled([apiClient.get('/auth/profile/'), apiClient.get('/catalog/tires/')]);
  await new Promise<void>((resolve) => setImmediate(resolve));
  pending.resolve({ data: { access: 'new-access', refresh: 'new-refresh' } });
  assert.deepEqual((await requests).map((result) => result.status), ['rejected', 'rejected']);
  assert.equal(refreshes, 1);
  assert.equal(attempts, 4);
});

test('logout after access expiry revokes the rotated refresh token, not its blacklisted predecessor', async (t) => {
  const bodies: any[] = [];
  const { apiClient } = setup(t, async (config) => {
    const data = JSON.parse(String(config.data));
    bodies.push(data);
    if (config.headers.Authorization === 'Bearer old-access') return rejectRequest(config);
    if (data.refresh !== 'new-refresh') return rejectRequest(config, 400);
    return response(config, { detail: 'Logged out' });
  }, async () => ({ data: { access: 'new-access', refresh: 'new-refresh' } }));
  const result = await apiClient.post('/auth/logout/', { refresh: 'old-refresh' });
  assert.equal(result.status, 200);
  assert.deepEqual(bodies, [{ refresh: 'old-refresh' }, { refresh: 'new-refresh' }]);
});

for (const [label, failure] of [
  ['network outage', () => new AxiosError('Network Error', 'ERR_NETWORK')],
  ['server error', () => new AxiosError('Server error', 'ERR_BAD_RESPONSE', undefined, undefined, { status: 503, data: {}, statusText: '503', headers: {}, config: {} as InternalAxiosRequestConfig })],
  ['refresh throttling', () => new AxiosError('Throttled', 'ERR_BAD_REQUEST', undefined, undefined, { status: 429, data: {}, statusText: '429', headers: {}, config: {} as InternalAxiosRequestConfig })],
] as const) {
  test(`refresh ${label} rejects the request but keeps the local session`, async (t) => {
    const { apiClient, values, location } = setup(t, rejectRequest, async () => { throw failure(); });
    await assert.rejects(apiClient.get('/auth/profile/'));
    assert.equal(values.get('access_token'), 'old-access');
    assert.equal(values.get('refresh_token'), 'old-refresh');
    assert.equal(location.href, '/dashboard');
  });
}
