import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';
import { deferred, loadComponent } from './componentHarness.ts';

function response(config: InternalAxiosRequestConfig, data: any = {}, status = 200) {
  return { config, data, status, statusText: String(status), headers: {} };
}
function rejectRequest(config: InternalAxiosRequestConfig, status = 401) {
  return Promise.reject(new AxiosError('Request rejected', 'ERR_BAD_REQUEST', config, undefined, response(config, {}, status)));
}
function createStorageMock(values: Map<string, string>) {
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  };
}

function setup(
  t: TestContext,
  adapter: AxiosAdapter,
  refresh: (url: string, data: any) => Promise<any>,
  env: Record<string, string> = {},
  mode: 'session' | 'persistent' = 'session',
) {
  const initialEntries: Array<[string, string]> = [
    ['access_token', 'old-access'],
    ['refresh_token', 'old-refresh'],
    ['user_info', '{}'],
    ['last_activity_at', String(Date.now() - 10_000)],
  ];
  const sessionValues = new Map<string, string>(mode === 'session' ? initialEntries : []);
  const localValues = new Map<string, string>(
    mode === 'persistent' ? [...initialEntries, ['auth_persistence', 'persistent']] : [],
  );
  const values = mode === 'persistent' ? localValues : sessionValues;
  const location = { href: '/dashboard' };
  const descriptors = ['localStorage', 'sessionStorage', 'window'].map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)] as const);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: createStorageMock(localValues) });
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: createStorageMock(sessionValues) });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { location } });
  t.after(() => {
    for (const [key, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  });
  const authStorage = loadComponent('../src/utils/authStorage.ts', {}, env);
  const { apiClient, API_BASE_URL } = loadComponent('../src/api/client.ts', {
    axios: { create: (config: any) => axios.create({ ...config, adapter }), post: refresh },
    '../utils/authStorage': authStorage,
    '../utils/errorParser': { parseApiError: () => 'Request rejected' },
  }, env);
  return { apiClient, API_BASE_URL, values, sessionValues, localValues, location };
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
  const prevActivity = Number(values.get('last_activity_at'));
  const requests = [apiClient.get('/auth/profile/'), apiClient.get('/catalog/tires/')];
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.deepEqual(refreshes, [{ url: '/api/v1/auth/token/refresh/', data: { refresh: 'old-refresh' } }]);
  pending.resolve({ data: { access: 'new-access', refresh: 'new-refresh' } });
  await Promise.all(requests);
  assert.equal(attempts.length, 4);
  assert.equal(attempts.filter((attempt) => attempt.token === 'Bearer new-access').length, 2);
  assert.equal(values.get('access_token'), 'new-access');
  assert.equal(values.get('refresh_token'), 'new-refresh');
  assert.ok(Number(values.get('last_activity_at')) >= prevActivity);
});

test('refresh rejection rejects queued requests and clears the local session', async (t) => {
  const pending = deferred<any>();
  const { apiClient, values, location } = setup(t, rejectRequest, () => pending.promise);
  const requests = Promise.allSettled([apiClient.get('/auth/profile/'), apiClient.get('/catalog/tires/')]);
  await new Promise<void>((resolve) => setImmediate(resolve));
  pending.reject(new Error('Refresh revoked'));
  assert.deepEqual((await requests).map((result) => result.status), ['rejected', 'rejected']);
  assert.equal(values.size, 0);
  assert.equal(location.href, '/login?reason=session-expired');
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
  assert.equal(location.href, '/login?reason=session-expired');
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

for (const mode of ['session', 'persistent'] as const) {
  test(`navigator.locks coordinates cross-tab refresh in ${mode} mode and skips duplicate refresh POST`, async (t) => {
    const navDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
    let lockRequests = 0;
    let refreshes = 0;
    const attempts: string[] = [];

    const { apiClient, values, sessionValues, localValues } = setup(t, async (config) => {
      attempts.push(String(config.headers.Authorization));
      if (config.headers.Authorization === 'Bearer old-access') return rejectRequest(config);
      return response(config, { ok: true });
    }, async () => {
      refreshes++;
      return { data: { access: 'unexpected-access' } };
    }, {}, mode);

    const prevActivity = Number(values.get('last_activity_at'));
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: {
        locks: {
          request: async (_name: string, cb: () => Promise<unknown>) => {
            lockRequests++;
            values.set('access_token', 'tab-b-access');
            values.set('refresh_token', 'tab-b-refresh');
            return cb();
          },
        },
      },
    });
    t.after(() => {
      if (navDescriptor) Object.defineProperty(globalThis, 'navigator', navDescriptor);
      else Reflect.deleteProperty(globalThis, 'navigator');
    });

    const res = await apiClient.get('/auth/profile/');
    assert.equal(res.status, 200);
    assert.equal(lockRequests, 1);
    assert.equal(refreshes, 0);
    assert.deepEqual(attempts, ['Bearer old-access', 'Bearer tab-b-access']);
    assert.equal(apiClient.defaults.headers.common.Authorization, 'Bearer tab-b-access');
    assert.ok(Number(values.get('last_activity_at')) >= prevActivity);
    if (mode === 'session') {
      assert.equal(localValues.size, 0);
    } else {
      assert.equal(sessionValues.size, 0);
    }
  });
}

test('fallback refresh error adopts concurrent storage rotation instead of clearing session', async (t) => {
  const navDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: undefined });
  t.after(() => {
    if (navDescriptor) Object.defineProperty(globalThis, 'navigator', navDescriptor);
    else Reflect.deleteProperty(globalThis, 'navigator');
  });

  const attempts: string[] = [];
  const { apiClient, values, location } = setup(t, async (config) => {
    attempts.push(String(config.headers.Authorization));
    if (config.headers.Authorization === 'Bearer old-access') return rejectRequest(config);
    return response(config, { ok: true });
  }, async () => {
    values.set('access_token', 'rotated-access');
    values.set('refresh_token', 'rotated-refresh');
    throw new Error('Refresh token blacklisted by concurrent tab');
  }, {}, 'persistent');

  const res = await apiClient.get('/auth/profile/');
  assert.equal(res.status, 200);
  assert.deepEqual(attempts, ['Bearer old-access', 'Bearer rotated-access']);
  assert.equal(values.get('access_token'), 'rotated-access');
  assert.equal(values.get('refresh_token'), 'rotated-refresh');
  assert.equal(location.href, '/dashboard');
});

test('apiClient purges legacy unflagged localStorage tokens and updates activity on successful responses', async (t) => {
  const seenAuthHeaders: Array<string | undefined> = [];
  const { apiClient, localValues, sessionValues } = setup(t, async (config) => {
    seenAuthHeaders.push(config.headers.Authorization ? String(config.headers.Authorization) : undefined);
    return response(config, { ok: true });
  }, async () => ({}));

  sessionValues.clear();
  localValues.set('access_token', 'legacy-local-access');
  localValues.set('refresh_token', 'legacy-local-refresh');
  localValues.set('preferred_currency', 'rial');

  await apiClient.get('/catalog/tires/');
  assert.deepEqual(seenAuthHeaders, [undefined]);
  assert.equal(localValues.get('access_token'), undefined);
  assert.equal(localValues.get('refresh_token'), undefined);
  assert.equal(localValues.get('preferred_currency'), 'rial');

  sessionValues.set('access_token', 'valid-session-access');
  sessionValues.set('last_activity_at', '1000');
  await apiClient.get('/catalog/tires/');
  assert.equal(seenAuthHeaders[1], 'Bearer valid-session-access');
  assert.ok(Number(sessionValues.get('last_activity_at')) > 1000);
});

test('multi-tab lock releases before replaying original request so concurrent 401 uses rotated token without deadlock', async (t) => {
  let inLock = false;
  let lockRequests = 0;
  let refreshes = 0;
  const navDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: {
      locks: {
        request: async (_name: string, callback: () => Promise<unknown>) => {
          lockRequests++;
          inLock = true;
          try {
            return await callback();
          } finally {
            inLock = false;
          }
        },
      },
    },
  });
  t.after(() => {
    if (navDescriptor) Object.defineProperty(globalThis, 'navigator', navDescriptor);
    else Reflect.deleteProperty(globalThis, 'navigator');
  });

  const replay1 = deferred<any>();
  const firstReplayStarted = deferred<void>();
  const secondAdapterInFlight = deferred<void>();
  const releaseSecond401 = deferred<void>();
  let secondRequestSettledBeforeFirstReplay = false;
  let firstConfig!: InternalAxiosRequestConfig;

  const { apiClient } = setup(
    t,
    async (config) => {
      if (config.url === '/second/' && config.headers.Authorization === 'Bearer old-access') {
        secondAdapterInFlight.resolve();
        await releaseSecond401.promise;
        return rejectRequest(config);
      }
      if (config.headers.Authorization === 'Bearer old-access') {
        return rejectRequest(config);
      }
      if (config.url === '/first/') {
        assert.equal(inLock, false, 'Web Lock must be released before replaying original request');
        firstConfig = config;
        firstReplayStarted.resolve();
        return replay1.promise;
      }
      return response(config, { url: config.url, ok: true });
    },
    async () => {
      refreshes++;
      return { data: { access: 'new-access-1', refresh: 'new-refresh-1' } };
    },
  );

  const req2 = apiClient
    .get('/second/')
    .then((res: any) => {
      secondRequestSettledBeforeFirstReplay = true;
      return res;
    });
  await secondAdapterInFlight.promise;

  const req1 = apiClient.get('/first/');
  await firstReplayStarted.promise;

  releaseSecond401.resolve();
  const res2 = await req2;
  assert.equal(res2.status, 200);
  assert.equal(secondRequestSettledBeforeFirstReplay, true);

  replay1.resolve(response(firstConfig, { url: '/first/', ok: true }));
  const res1 = await req1;
  assert.equal(res1.status, 200);
  assert.equal(refreshes, 1);
  assert.equal(lockRequests, 2);
});
