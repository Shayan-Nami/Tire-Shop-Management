import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import { parseApiError } from '../src/utils/errorParser.ts';
import * as storageModule from '../src/utils/storage.ts';
import { deferred, loadComponent, mountComponent, nodes, text } from './componentHarness.ts';

type Harness = ReturnType<typeof mountComponent>;

function find(h: Harness, predicate: (node: any) => boolean) {
  const result = nodes(h.tree, predicate)[0];
  assert.ok(result, 'Expected authentication control was not found');
  return result;
}

function browserSession(t: TestContext) {
  const values = new Map([
    ['access_token', 'old-access'], ['refresh_token', 'old-refresh'],
    ['user_info', JSON.stringify({ id: 1, username: 'manager', role: 'MANAGER' })],
    ['preferred_currency', 'toman'],
  ]);
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
  const location = { href: '/dashboard', search: '' };
  const descriptors = ['localStorage', 'window'].map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage });
  const listeners = new Map<string, (event: any) => void>();
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    location,
    addEventListener: (type: string, listener: (event: any) => void) => { listeners.set(type, listener); },
    removeEventListener: (type: string) => { listeners.delete(type); },
  } });
  t.after(() => {
    for (const [name, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  });
  return { values, storage, location, listeners };
}

async function setup(t: TestContext, changePassword: (payload: any) => Promise<unknown>, logout?: (token: string) => Promise<void>) {
  const browser = browserSession(t);
  const cachedHeaders: Record<string, string> = { Authorization: 'Bearer old-access' };
  const { clearLocalSession } = loadComponent('../src/utils/session.ts', {
    '../api/client': { apiClient: { defaults: { headers: { common: cachedHeaders } } } },
    './storage': storageModule,
  });
  const logoutTokens: string[] = [];
  const user = JSON.parse(browser.storage.getItem('user_info')!);
  const authApi = {
    getCurrentUser: async () => user,
    changePassword,
    logout: async (token: string) => { logoutTokens.push(token); await logout?.(token); },
  };
  const provider = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': { authApi },
    '../utils/session': { clearLocalSession },
    '../utils/storage': storageModule,
  });
  await provider.flush();
  let closed = 0;
  const modal = mountComponent('../src/components/auth/ChangePasswordModal.tsx', 'ChangePasswordModal', {
    '../../api/auth': { authApi },
    '../../utils/errorParser': { parseApiError },
    '../../context/AuthContext': { useAuth: () => provider.tree.props.value },
  }, { isOpen: true, onClose: () => { closed++; } });
  t.after(() => { modal.unmount(); provider.unmount(); });
  await modal.flush();
  return { ...browser, cachedHeaders, logoutTokens, provider, modal, closed: () => closed };
}

function fillPasswords(h: Harness, nextPassword = 'new-password-123') {
  for (const [index, value] of ['old-password-123', nextPassword, nextPassword].entries()) {
    const input = nodes(h.tree, (node) => node.type === 'input' && node.props.type === 'password')[index];
    assert.ok(input);
    input.props.onChange({ target: { value } });
    h.render();
  }
}

const send = (h: Harness) => find(h, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });

function assertSessionCleared(session: Awaited<ReturnType<typeof setup>>, destination: string) {
  for (const key of ['access_token', 'refresh_token', 'user_info']) assert.equal(session.storage.getItem(key), null);
  assert.equal(session.storage.getItem('preferred_currency'), 'toman');
  assert.equal(session.cachedHeaders.Authorization, undefined);
  assert.equal(session.provider.tree.props.value.user, null);
  assert.equal(session.provider.tree.props.value.isAuthenticated, false);
  assert.equal(session.location.href, destination);
}

test('password-change success immediately ends the local session without logout or refresh', async (t) => {
  const pending = deferred<any>();
  const payloads: any[] = [];
  const session = await setup(t, (payload) => { payloads.push(payload); return pending.promise; });
  fillPasswords(session.modal);
  const sending = send(session.modal);
  await session.modal.flush();
  assert.equal(session.storage.getItem('access_token'), 'old-access');
  assert.equal(find(session.modal, (node) => node.type === 'button' && node.props.type === 'submit').props.disabled, true);
  pending.resolve({ detail: 'Password changed successfully.' });
  await sending;
  await session.provider.flush();
  await session.modal.flush();
  assert.deepEqual(payloads, [{ old_password: 'old-password-123', new_password: 'new-password-123' }]);
  assertSessionCleared(session, '/login?reason=password-changed');
  assert.deepEqual(session.logoutTokens, []);
  assert.equal(session.closed(), 0);
});

test('password-change server failure shows an error and preserves the local session', async (t) => {
  const session = await setup(t, async () => { throw new Error('Current password is incorrect'); });
  fillPasswords(session.modal);
  await send(session.modal);
  await session.modal.flush();
  await session.provider.flush();
  assert.match(text(find(session.modal, (node) => node.props?.role === 'alert')), /Current password is incorrect/);
  assert.equal(session.storage.getItem('access_token'), 'old-access');
  assert.equal(session.storage.getItem('refresh_token'), 'old-refresh');
  assert.notEqual(session.storage.getItem('user_info'), null);
  assert.equal(session.provider.tree.props.value.isAuthenticated, true);
  assert.equal(session.cachedHeaders.Authorization, 'Bearer old-access');
  assert.equal(session.location.href, '/dashboard');
  assert.deepEqual(session.logoutTokens, []);
  assert.equal(session.closed(), 0);
  assert.equal(find(session.modal, (node) => node.type === 'button' && node.props.type === 'submit').props.disabled, false);
});

test('password-change validation failure does not call the server or end the session', async (t) => {
  let calls = 0;
  const session = await setup(t, async () => { calls++; return {}; });
  fillPasswords(session.modal, 'short');
  await send(session.modal);
  await session.modal.flush();
  assert.equal(calls, 0);
  assert.match(text(find(session.modal, (node) => node.props?.role === 'alert')), /۸ کاراکتر/);
  assert.equal(session.storage.getItem('access_token'), 'old-access');
  assert.equal(session.location.href, '/dashboard');
  assert.deepEqual(session.logoutTokens, []);
});

for (const serverFails of [false, true]) {
  test(`normal logout still contacts the server and clears locally when it ${serverFails ? 'fails' : 'succeeds'}`, async (t) => {
    const pending = deferred<void>();
    t.mock.method(console, 'warn', () => {});
    const session = await setup(t, async () => ({}), () => pending.promise);
    const signingOut = session.provider.tree.props.value.logout();
    assert.deepEqual(session.logoutTokens, ['old-refresh']);
    assert.equal(session.storage.getItem('access_token'), 'old-access');
    assert.equal(session.location.href, '/dashboard');
    if (serverFails) pending.reject(new Error('Server unavailable'));
    else pending.resolve();
    await signingOut;
    await session.provider.flush();
    assertSessionCleared(session, '/login');
  });
}

test('login explains password-change re-login, but not for ordinary visits', async (t) => {
  const browser = browserSession(t);
  const mount = () => mountComponent('../src/pages/Login.tsx', 'Login', {
    '../context/AuthContext': { useAuth: () => ({ isAuthenticated: false, user: null }) },
    '../utils/errorParser': { parseApiError },
    'react-router-dom': { useNavigate: () => () => {} },
  });
  const ordinary = mount();
  assert.equal(nodes(ordinary.tree, (node) => node.props?.role === 'status').length, 0);
  ordinary.unmount();
  browser.location.search = '?reason=password-changed';
  const changed = mount();
  t.after(() => changed.unmount());
  const message = text(find(changed, (node) => node.props?.role === 'status'));
  assert.match(message, /نشست شما پایان یافت/);
  assert.match(message, /کلمه عبور جدید دوباره وارد شوید/);
});

test('profile outage at startup keeps the cached session; a rejected session is cleared', async (t) => {
  const browser = browserSession(t);
  const initial = new Map(browser.values);
  for (const [status, keepsSession] of [[undefined, true], [503, true], [401, false]] as const) {
    for (const [key, value] of initial) browser.values.set(key, value);
    const failure = Object.assign(new Error('profile failed'), status ? { response: { status } } : {});
    const provider = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
      '../api/auth': { authApi: { getCurrentUser: async () => { throw failure; } } },
      '../utils/session': { clearLocalSession() {} },
      '../utils/storage': storageModule,
    });
    await provider.flush();
    assert.equal(provider.tree.props.value.isAuthenticated, keepsSession, `status ${status}`);
    assert.equal(browser.storage.getItem('refresh_token'), keepsSession ? 'old-refresh' : null);
    provider.unmount();
  }
});

test('signing out in another tab ends this tab session', async (t) => {
  const session = await setup(t, async () => ({}));
  assert.equal(session.provider.tree.props.value.isAuthenticated, true);
  for (const key of ['access_token', 'refresh_token', 'user_info']) session.storage.removeItem(key);
  session.listeners.get('storage')?.({ key: 'access_token', newValue: null });
  await session.provider.flush();
  assert.equal(session.provider.tree.props.value.isAuthenticated, false);
  assert.equal(session.location.href, '/login');
});
