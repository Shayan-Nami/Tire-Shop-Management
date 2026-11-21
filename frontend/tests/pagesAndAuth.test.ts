import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import { parseApiError } from '../src/utils/errorParser.ts';
import * as formatters from '../src/utils/formatters.ts';
import { translations } from '../src/utils/i18n.ts';
import { createRequestSequence } from '../src/utils/invoiceRequests.ts';
import { deferred, loadComponent, mountComponent, nodes, page, text } from './componentHarness.ts';

function find(tree: any, predicate: (node: any) => boolean) {
  const node = nodes(tree, predicate)[0];
  assert.ok(node, 'Expected control or element was not found');
  return node;
}

function createStorageMock(values: Map<string, string>) {
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

function setupBrowserGlobals(
  t: TestContext,
  initialLocalStorage: Record<string, string> = {},
  initialSessionStorage: Record<string, string> = {},
) {
  const values = new Map<string, string>(Object.entries(initialLocalStorage));
  const sessionValues = new Map<string, string>(Object.entries(initialSessionStorage));
  const listeners = new Map<string, Set<(event: any) => void>>();
  const docListeners = new Map<string, Set<(event: any) => void>>();
  const storage = createStorageMock(values);
  const sessionStorageMock = createStorageMock(sessionValues);
  const win = {
    location: { href: '/', pathname: '/', search: '' },
    addEventListener(type: string, fn: (event: any) => void) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(fn);
    },
    removeEventListener(type: string, fn: (event: any) => void) {
      listeners.get(type)?.delete(fn);
    },
    dispatchEvent(type: string, event: any = {}) {
      for (const fn of [...(listeners.get(type) ?? [])]) fn(event);
    },
    dispatchStorage(event: { key: string | null; newValue?: string | null }) {
      for (const fn of [...(listeners.get('storage') ?? [])]) fn(event);
    },
  };
  const doc = {
    visibilityState: 'visible',
    addEventListener(type: string, fn: (event: any) => void) {
      if (!docListeners.has(type)) docListeners.set(type, new Set());
      docListeners.get(type)!.add(fn);
    },
    removeEventListener(type: string, fn: (event: any) => void) {
      docListeners.get(type)?.delete(fn);
    },
    dispatchVisibilityChange(visibilityState: 'visible' | 'hidden') {
      doc.visibilityState = visibilityState;
      for (const fn of [...(docListeners.get('visibilitychange') ?? [])]) fn({});
    },
  };
  const descriptors = ['localStorage', 'sessionStorage', 'window', 'document'].map(
    (name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const,
  );
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage });
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: sessionStorageMock });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: win });
  Object.defineProperty(globalThis, 'document', { configurable: true, value: doc });
  t.after(() => {
    for (const [name, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  });
  return { values, sessionValues, win, doc, listeners, docListeners };
}

function loadSessionBundle(env: Record<string, string> = {}) {
  const cachedHeaders: Record<string, string> = {};
  const authStorage = loadComponent('../src/utils/authStorage.ts', {}, env);
  const sessionUtils = loadComponent('../src/utils/session.ts', {
    '../api/client': { apiClient: { defaults: { headers: { common: cachedHeaders } } } },
    './authStorage': authStorage,
  }, env);
  return { authStorage, sessionUtils: { ...authStorage, ...sessionUtils }, cachedHeaders };
}

test('authStorage validates idle timeout bounds, last_activity_at, and legacy localStorage cleanup', (t) => {
  const { values } = setupBrowserGlobals(t, {
    access_token: 'legacy-tok',
    refresh_token: 'legacy-ref',
    user_info: JSON.stringify({ id: 1, username: 'ali', role: 'MANAGER' }),
    preferred_currency: 'rial',
    language: 'en',
  });
  const { authStorage } = loadSessionBundle({ VITE_IDLE_TIMEOUT_MINUTES: '20' });

  assert.equal(authStorage.parseIdleTimeoutMinutes(undefined), 15);
  assert.equal(authStorage.parseIdleTimeoutMinutes(null), 15);
  assert.equal(authStorage.parseIdleTimeoutMinutes(''), 15);
  assert.equal(authStorage.parseIdleTimeoutMinutes('0'), 15);
  assert.equal(authStorage.parseIdleTimeoutMinutes('-5'), 15);
  assert.equal(authStorage.parseIdleTimeoutMinutes('NaN'), 15);
  assert.equal(authStorage.parseIdleTimeoutMinutes('Infinity'), 15);
  assert.equal(authStorage.parseIdleTimeoutMinutes('0.5'), 0.5);
  assert.equal(authStorage.getIdleTimeoutMs(), 20 * 60_000);

  assert.equal(authStorage.getAccessToken(), null);
  assert.equal(values.get('access_token'), undefined);
  assert.equal(values.get('refresh_token'), undefined);
  assert.equal(values.get('user_info'), undefined);
  assert.equal(values.get('preferred_currency'), 'rial');
  assert.equal(values.get('language'), 'en');

  assert.equal(authStorage.isIdleExpired(null, 1_000_000, 900_000), true);
  assert.equal(authStorage.isIdleExpired(Number.NaN, 1_000_000, 900_000), true);
  assert.equal(authStorage.isIdleExpired(100_000, 999_999, 900_000), false);
  assert.equal(authStorage.isIdleExpired(100_000, 1_000_000, 900_000), true);
});

test('AuthContext syncs user and currency across tabs via storage events in persistent mode', async (t) => {
  const { win, values } = setupBrowserGlobals(t, {
    access_token: 'tok-1',
    refresh_token: 'ref-1',
    user_info: JSON.stringify({ id: 1, username: 'ali', role: 'MANAGER' }),
    preferred_currency: 'toman',
    auth_persistence: 'persistent',
    last_activity_at: String(Date.now()),
  });
  const { sessionUtils } = loadSessionBundle();
  const h = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': { authApi: { getCurrentUser: async () => ({ id: 1, username: 'ali', role: 'MANAGER' }), logout: async () => {} } },
    '../utils/session': sessionUtils,
  });
  t.after(() => h.unmount());
  await h.flush();

  assert.equal(h.tree.props.value.user.username, 'ali');
  assert.equal(h.tree.props.value.currencyUnit, 'toman');

  win.dispatchStorage({
    key: 'user_info',
    newValue: JSON.stringify({ id: 1, username: 'ali', full_name: 'Ali Updated', role: 'MANAGER' }),
  });
  await h.flush();
  assert.equal(h.tree.props.value.user.full_name, 'Ali Updated');

  win.dispatchStorage({ key: 'preferred_currency', newValue: 'rial' });
  await h.flush();
  assert.equal(h.tree.props.value.currencyUnit, 'rial');

  sessionUtils.clearAuthStorage();
  assert.equal(values.get('preferred_currency'), 'toman');
  win.dispatchStorage({ key: 'access_token', newValue: null });
  await h.flush();
  assert.equal(h.tree.props.value.user, null);
  assert.equal(h.tree.props.value.isAuthenticated, false);
});

test('AuthContext defaults login to sessionStorage and isolates session mode from localStorage storage events', async (t) => {
  const { values, sessionValues, win } = setupBrowserGlobals(t, { preferred_currency: 'toman' });
  const { sessionUtils } = loadSessionBundle();
  const h = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': {
      authApi: {
        login: async () => ({
          access: 'sess-access',
          refresh: 'sess-refresh',
          user: { id: 2, username: 'tech', role: 'TECHNICIAN' },
        }),
        getCurrentUser: async () => ({ id: 2, username: 'tech', role: 'TECHNICIAN' }),
        logout: async () => {},
      },
    },
    '../utils/session': sessionUtils,
  });
  t.after(() => h.unmount());
  await h.flush();

  await h.tree.props.value.login('tech', 'pass123');
  await h.flush();

  assert.equal(sessionValues.get('access_token'), 'sess-access');
  assert.equal(sessionValues.get('refresh_token'), 'sess-refresh');
  assert.ok(Number(sessionValues.get('last_activity_at')) > 0);
  assert.equal(values.get('access_token'), undefined);
  assert.equal(values.get('auth_persistence'), undefined);

  win.dispatchStorage({
    key: 'user_info',
    newValue: JSON.stringify({ id: 9, username: 'other', role: 'MANAGER' }),
  });
  win.dispatchStorage({ key: null });
  win.dispatchStorage({ key: 'preferred_currency', newValue: 'rial' });
  await h.flush();

  assert.equal(h.tree.props.value.isAuthenticated, true);
  assert.equal(h.tree.props.value.user.username, 'tech');
  assert.equal(h.tree.props.value.currencyUnit, 'rial');
});

test('AuthContext rememberMe=true persists session to localStorage with auth_persistence flag', async (t) => {
  const { values, sessionValues } = setupBrowserGlobals(t);
  const { sessionUtils } = loadSessionBundle();
  const h = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': {
      authApi: {
        login: async () => ({
          access: 'pers-access',
          refresh: 'pers-refresh',
          user: { id: 1, username: 'boss', role: 'MANAGER' },
        }),
        getCurrentUser: async () => ({ id: 1, username: 'boss', role: 'MANAGER' }),
        logout: async () => {},
      },
    },
    '../utils/session': sessionUtils,
  });
  t.after(() => h.unmount());
  await h.flush();

  await h.tree.props.value.login('boss', 'pass123', true);
  await h.flush();

  assert.equal(values.get('auth_persistence'), 'persistent');
  assert.equal(values.get('access_token'), 'pers-access');
  assert.equal(values.get('refresh_token'), 'pers-refresh');
  assert.ok(Number(values.get('last_activity_at')) > 0);
  assert.equal(sessionValues.size, 0);
});

test('AuthContext initAuth rejects expired last_activity_at before calling getCurrentUser and redirects with idle-timeout', async (t) => {
  const now = 1_700_000_000_000;
  t.mock.timers.enable({ apis: ['Date', 'setTimeout', 'setInterval'], now });
  const { values, sessionValues, win } = setupBrowserGlobals(
    t,
    { preferred_currency: 'rial' },
    {
      access_token: 'stale-access',
      refresh_token: 'stale-refresh',
      user_info: JSON.stringify({ id: 1, username: 'ali', role: 'MANAGER' }),
      last_activity_at: String(now - 16 * 60_000),
    },
  );
  win.location.pathname = '/dashboard';
  win.location.href = '/dashboard';

  let getCurrentUserCalls = 0;
  const { sessionUtils } = loadSessionBundle();
  const h = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': {
      authApi: {
        getCurrentUser: async () => { getCurrentUserCalls++; return { id: 1, username: 'ali', role: 'MANAGER' }; },
        logout: async () => {},
      },
    },
    '../utils/session': sessionUtils,
  });
  t.after(() => h.unmount());
  await h.flush();

  assert.equal(getCurrentUserCalls, 0);
  assert.equal(h.tree.props.value.user, null);
  assert.equal(h.tree.props.value.isAuthenticated, false);
  assert.equal(h.tree.props.value.isLoading, false);
  assert.equal(sessionValues.size, 0);
  assert.equal(values.get('preferred_currency'), 'rial');
  assert.equal(win.location.href, '/login?reason=idle-timeout');
});

test('AuthContext sleep-resilient idle monitor expires on wake activity without resetting last_activity_at', async (t) => {
  const startNow = 1_700_000_000_000;
  t.mock.timers.enable({ apis: ['Date', 'setTimeout', 'setInterval'], now: startNow });
  const { sessionValues, win, doc } = setupBrowserGlobals(t, {}, {
    access_token: 'sess-access',
    refresh_token: 'sess-refresh',
    user_info: JSON.stringify({ id: 1, username: 'ali', role: 'MANAGER' }),
    last_activity_at: String(startNow),
  });
  win.location.pathname = '/dashboard';
  win.location.href = '/dashboard';

  const logoutCalls: string[] = [];
  const { sessionUtils } = loadSessionBundle();
  const h = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': {
      authApi: {
        getCurrentUser: async () => ({ id: 1, username: 'ali', role: 'MANAGER' }),
        logout: async (refresh: string) => { logoutCalls.push(refresh); },
      },
    },
    '../utils/session': sessionUtils,
  });
  t.after(() => h.unmount());
  await h.flush();

  t.mock.timers.setTime(startNow + 20_000);
  win.dispatchEvent('mousemove');
  assert.equal(sessionValues.get('last_activity_at'), String(startNow + 20_000));

  t.mock.timers.setTime(startNow + 25_000);
  win.dispatchEvent('mousemove');
  assert.equal(sessionValues.get('last_activity_at'), String(startNow + 20_000));

  t.mock.timers.setTime(startNow + 20_000 + 16 * 60_000);
  win.dispatchEvent('mousemove');
  doc.dispatchVisibilityChange('visible');
  assert.equal(sessionValues.get('last_activity_at'), String(startNow + 20_000));

  await h.flush();
  assert.deepEqual(logoutCalls, ['sess-refresh']);
  assert.equal(sessionValues.size, 0);
  assert.equal(h.tree.props.value.user, null);
  assert.equal(win.location.href, '/login?reason=idle-timeout');
});

test('AuthContext idle monitor honors activity from another tab before expiring persistent session', async (t) => {
  const startNow = 1_700_000_000_000;
  t.mock.timers.enable({ apis: ['Date', 'setTimeout', 'setInterval'], now: startNow });
  const { values, win } = setupBrowserGlobals(t, {
    auth_persistence: 'persistent',
    access_token: 'pers-access',
    refresh_token: 'pers-refresh',
    user_info: JSON.stringify({ id: 1, username: 'ali', role: 'MANAGER' }),
    last_activity_at: String(startNow),
  });
  win.location.pathname = '/dashboard';
  win.location.href = '/dashboard';

  const logoutCalls: string[] = [];
  const { sessionUtils } = loadSessionBundle({ VITE_IDLE_TIMEOUT_MINUTES: '1' });
  const h = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': {
      authApi: {
        getCurrentUser: async () => ({ id: 1, username: 'ali', role: 'MANAGER' }),
        logout: async (refresh: string) => { logoutCalls.push(refresh); },
      },
    },
    '../utils/session': sessionUtils,
  });
  t.after(() => h.unmount());
  await h.flush();

  t.mock.timers.tick(50_000);
  values.set('last_activity_at', String(startNow + 50_000));
  t.mock.timers.tick(20_000);
  await h.flush();

  assert.deepEqual(logoutCalls, []);
  assert.equal(h.tree.props.value.isAuthenticated, true);

  t.mock.timers.tick(50_000);
  await h.flush();
  assert.deepEqual(logoutCalls, ['pers-refresh']);
  assert.equal(h.tree.props.value.isAuthenticated, false);
  assert.equal(win.location.href, '/login?reason=idle-timeout');
});

test('Login waits for auth initialization before redirecting authenticated users', (t) => {
  setupBrowserGlobals(t);
  let isLoading = true;
  const navigations: Array<{ to: string; opts: unknown }> = [];
  const h = mountComponent('../src/pages/Login.tsx', 'Login', {
    '../context/AuthContext': {
      useAuth: () => ({ login: async () => {}, isAuthenticated: true, isLoading, user: { id: 1, role: 'MANAGER' } }),
    },
    '../utils/errorParser': { parseApiError },
    'react-router-dom': { useNavigate: () => (to: string, opts: unknown) => navigations.push({ to, opts }) },
  });
  t.after(() => h.unmount());

  assert.deepEqual(navigations, []);
  const arrow = find(h.tree, (node) => node.type === 'ArrowLeft');
  assert.match(arrow.props.className, /\bltr:rotate-180\b/);

  isLoading = false;
  h.render();
  assert.deepEqual(navigations, [{ to: '/', opts: { replace: true } }]);
});

test('Login Remember Me checkbox defaults to false, passes selection to login, and renders reason banners', async (t) => {
  const { win } = setupBrowserGlobals(t);
  const loginCalls: Array<{ username: string; password: string; rememberMe: boolean }> = [];
  const mountLogin = () => mountComponent('../src/pages/Login.tsx', 'Login', {
    '../context/AuthContext': {
      useAuth: () => ({
        login: async (username: string, password: string, rememberMe = false) => {
          loginCalls.push({ username, password, rememberMe });
        },
        isAuthenticated: false,
        isLoading: false,
        user: null,
      }),
    },
    '../utils/errorParser': { parseApiError },
    'react-router-dom': { useNavigate: () => () => {} },
  });

  const h = mountLogin();
  const checkbox = find(h.tree, (node) => node.type === 'input' && node.props.id === 'login-remember-me');
  const label = find(h.tree, (node) => node.type === 'label' && node.props.htmlFor === 'login-remember-me');
  assert.equal(checkbox.props.checked, false);
  assert.match(text(label), /مرا به خاطر بسپار/);

  find(h.tree, (node) => node.type === 'input' && node.props.id === 'login-username').props.onChange({ target: { value: 'ali' } });
  find(h.tree, (node) => node.type === 'input' && node.props.id === 'login-password').props.onChange({ target: { value: 'secret123' } });
  h.render();

  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.deepEqual(loginCalls, [{ username: 'ali', password: 'secret123', rememberMe: false }]);

  find(h.tree, (node) => node.type === 'input' && node.props.id === 'login-remember-me').props.onChange({ target: { checked: true } });
  h.render();
  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.deepEqual(loginCalls[1], { username: 'ali', password: 'secret123', rememberMe: true });
  h.unmount();

  win.location.search = '?reason=idle-timeout';
  const idleLogin = mountLogin();
  assert.match(text(find(idleLogin.tree, (node) => node.props?.role === 'status')), /عدم فعالیت پایان یافت/);
  idleLogin.unmount();

  win.location.search = '?reason=session-expired';
  const expiredLogin = mountLogin();
  t.after(() => expiredLogin.unmount());
  assert.match(text(find(expiredLogin.tree, (node) => node.props?.role === 'status')), /اعتبار نشست شما به پایان رسیده است/);
});

test('ProfileModal cleans up auto-close timer on unmount and uses logical LTR padding for phone', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let closed = 0;
  const user = { id: 1, username: 'manager', full_name: 'Manager', phone_number: '09120000000', role: 'MANAGER' };
  const h = mountComponent('../src/components/auth/ProfileModal.tsx', 'ProfileModal', {
    '../../context/AuthContext': { useAuth: () => ({ user, updateUser() {} }) },
    '../../api/auth': { authApi: { updateProfile: async () => user } },
    '../../utils/errorParser': { parseApiError },
  }, { isOpen: true, onClose: () => { closed++; } });

  const phoneInput = find(h.tree, (node) => node.type === 'input' && node.props.id === 'profile-phone-number');
  assert.match(phoneInput.props.className, /\bpe-3\.5\b/);
  assert.match(phoneInput.props.className, /\bps-9\b/);
  assert.ok(!phoneInput.props.className.includes('px-3.5'));

  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.equal(closed, 0);

  h.unmount();
  t.mock.timers.tick(2000);
  assert.equal(closed, 0);
});

test('RoleGuard uses accessible loading contrast and localizes role names cleanly', () => {
  const enLang = {
    language: 'en',
    t: (key: string) => translations[key]?.en || key,
  };
  let authState: any = { isLoading: true, isAuthenticated: false, user: null };
  const h = mountComponent('../src/components/layout/RoleGuard.tsx', 'RoleGuard', {
    '../../context/LanguageContext': { useLanguage: () => enLang },
    '../../context/AuthContext': { useAuth: () => authState },
    'react-router-dom': { Navigate: 'navigate', Outlet: 'outlet', Link: 'a' },
  }, { allowedRoles: ['MANAGER'] });

  const spinnerText = find(h.tree, (node) => node.type === 'span');
  assert.equal(text(spinnerText), translations['در حال بارگذاری اطلاعات دسترسی...'].en);
  assert.match(spinnerText.props.className, /\btext-slate-200\b/);

  authState = {
    isLoading: false,
    isAuthenticated: true,
    user: { id: 2, username: 'tech', role: 'TECHNICIAN', role_display: 'تکنسین' },
  };
  h.render();
  const deniedText = text(h.tree);
  assert.match(deniedText, /Technician/);
  assert.ok(!deniedText.includes('تکنسین'));
  h.unmount();
});

test('Modal respects busy state on cancel and backdrop click', (t) => {
  const docDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'document');
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { activeElement: null } });
  t.after(() => {
    if (docDescriptor) Object.defineProperty(globalThis, 'document', docDescriptor);
    else Reflect.deleteProperty(globalThis, 'document');
  });

  let closed = 0;
  let busy = true;
  let h = mountComponent('../src/components/ui/Modal.tsx', 'Modal', {}, {
    onClose: () => { closed++; },
    label: 'Test dialog',
    busy,
    children: 'Body',
  });
  const dialogTarget = {};
  find(h.tree, (node) => node.type === 'dialog').props.ref.current = dialogTarget;

  let prevented = false;
  find(h.tree, (node) => node.type === 'dialog').props.onCancel({ preventDefault() { prevented = true; } });
  find(h.tree, (node) => node.type === 'dialog').props.onClick({ target: dialogTarget });
  assert.equal(prevented, true);
  assert.equal(closed, 0);
  h.unmount();

  busy = false;
  h = mountComponent('../src/components/ui/Modal.tsx', 'Modal', {}, {
    onClose: () => { closed++; },
    label: 'Test dialog',
    busy,
    children: 'Body',
  });
  find(h.tree, (node) => node.type === 'dialog').props.ref.current = dialogTarget;
  find(h.tree, (node) => node.type === 'dialog').props.onCancel({ preventDefault() {} });
  find(h.tree, (node) => node.type === 'dialog').props.onClick({ target: dialogTarget });
  assert.equal(closed, 2);
  h.unmount();
});

test('UsersPage disables self role/active controls, omits phantom role copy, and recovers from load error', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let shouldFail = true;
  const updates: Array<{ id: number; data: any }> = [];
  const staff = [
    { id: 1, username: 'boss', full_name: 'Shop Boss', phone_number: '09120000001', role: 'MANAGER', role_display: 'مدیر', is_active: true },
    { id: 2, username: 'tech', full_name: 'Tech One', phone_number: '09120000002', role: 'TECHNICIAN', role_display: 'تکنسین', is_active: true },
  ];
  const h = mountComponent('../src/pages/UsersPage.tsx', 'UsersPage', {
    '../api/auth': {
      authApi: {
        getUsers: async () => {
          if (shouldFail) throw new Error('users offline');
          return staff;
        },
        updateUser: async (id: number, data: any) => { updates.push({ id, data }); return staff[0]; },
      },
    },
    '../context/AuthContext': { useAuth: () => ({ user: staff[0] }) },
    '../utils/errorParser': { parseApiError },
  });
  t.after(() => h.unmount());
  await h.flush();

  const subtitle = text(find(h.tree, (node) => node.type === 'p'));
  assert.ok(!subtitle.includes('حسابدار'));

  const alert = find(h.tree, (node) => node.props?.role === 'alert');
  assert.match(text(alert), /users offline/);
  shouldFail = false;
  find(alert, (node) => node.type === 'button').props.onClick();
  await h.flush();
  assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);

  const editButtons = nodes(h.tree, (node) => node.type === 'button' && node.props['aria-label'] === 'ویرایش کاربر');
  assert.equal(editButtons.length, 2);

  editButtons[0].props.onClick();
  h.render();
  assert.equal(find(h.tree, (node) => node.type === 'select' && node.props.id === 'user-role').props.disabled, true);
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'userActive').props.disabled, true);
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'user-username').props.dir, 'ltr');
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'user-password').props.dir, 'ltr');
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'user-phone').props.dir, 'ltr');

  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.equal(updates[0].data.role, 'MANAGER');
  assert.equal(updates[0].data.is_active, true);

  nodes(h.tree, (node) => node.type === 'button' && node.props['aria-label'] === 'ویرایش کاربر')[1].props.onClick();
  h.render();
  assert.equal(find(h.tree, (node) => node.type === 'select' && node.props.id === 'user-role').props.disabled, false);
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'userActive').props.disabled, false);
});

for (const spec of [
  {
    name: 'Customers',
    apiKey: '../api/crm',
    apiValue: (fn: (params: any) => Promise<any>) => ({ crmApi: { getCustomers: fn } }),
    extras: { '../components/plates/IranianPlateBadge': { IranianPlateBadge: 'plate-badge' } },
    emptyRegex: /مشتری با این مشخصات یافت نشد/,
    sample: { customer_id: 1, full_name: 'Stale Customer', phone_number: '0912', vehicles: [] },
  },
  {
    name: 'ServicesPage',
    apiKey: '../api/services',
    apiValue: (fn: (params: any) => Promise<any>) => ({ servicesApi: { getServices: fn } }),
    extras: { '../utils/formatters': formatters },
    emptyRegex: /خدمتی با این مشخصات یافت نشد/,
    sample: { service_id: 1, service_name: 'Stale Service', price: 1000 },
  },
  {
    name: 'SuppliersPage',
    apiKey: '../api/suppliers',
    apiValue: (fn: (params: any) => Promise<any>) => ({ suppliersApi: { getSuppliers: fn } }),
    extras: {},
    emptyRegex: /تأمین‌کننده‌ای با این مشخصات یافت نشد/,
    sample: { supplier_id: 1, supplier_name: 'Stale Supplier' },
  },
  {
    name: 'StockMovements',
    apiKey: '../api/catalog',
    apiValue: (fn: (params: any) => Promise<any>) => ({ catalogApi: { getStockMovements: fn } }),
    extras: { '../utils/formatters': formatters },
    emptyRegex: /رکوردی یافت نشد/,
    sample: {
      movement_id: 1, tire_name: 'Stale Tire', brand_name: 'Brand',
      movement_type: 'SALE', movement_type_display: 'Sale',
      quantity: -1, balance_after: 4, created_at: '2026-11-02T12:00:00Z',
    },
  },
]) {
  test(`${spec.name} supports load error retry and ignores stale search responses`, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] });
    let phase: 'fail' | 'initial' | 'search' = 'fail';
    const initial = deferred<any>();
    const filtered = deferred<any>();
    const h = mountComponent(`../src/pages/${spec.name}.tsx`, spec.name, {
      [spec.apiKey]: spec.apiValue(async (params) => {
        if (phase === 'fail') throw new Error(`${spec.name} network failure`);
        return params.search ? filtered.promise : initial.promise;
      }),
      '../context/AuthContext': { useAuth: () => ({ user: { id: 1, role: 'MANAGER' }, currencyUnit: 'rial' }) },
      '../utils/errorParser': { parseApiError },
      '../utils/invoiceRequests': { createRequestSequence },
      ...spec.extras,
    });
    t.after(() => h.unmount());
    await h.flush();

    const alert = find(h.tree, (node) => node.props?.role === 'alert');
    assert.match(text(alert), new RegExp(`${spec.name} network failure`));

    phase = 'initial';
    find(alert, (node) => node.type === 'button').props.onClick();
    const search = find(h.tree, (node) => node.type === 'input' && node.props.placeholder?.startsWith('جستجو'));
    phase = 'search';
    search.props.onChange({ target: { value: 'missing' } });
    h.render();
    t.mock.timers.tick(300);
    await h.flush();

    filtered.resolve(page([]));
    await h.flush();
    assert.match(text(h.tree), spec.emptyRegex);

    initial.resolve(page([spec.sample]));
    await h.flush();
    assert.match(text(h.tree), spec.emptyRegex);
  });
}

test('ReportsPage ignores stale tab responses when switching tabs quickly', async (t) => {
  const profitability = deferred<any[]>();
  const inventory = deferred<any>();
  const h = mountComponent('../src/pages/ReportsPage.tsx', 'ReportsPage', {
    '../api/reports': {
      reportsApi: {
        getProfitability: () => profitability.promise,
        getInventoryValue: () => inventory.promise,
        getSalesByDateRange: async () => ({ total_invoices: 0, total_sales_amount: 0 }),
      },
    },
    '../utils/formatters': formatters,
    '../utils/errorParser': { parseApiError },
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../utils/invoiceRequests': { createRequestSequence },
  });
  t.after(() => h.unmount());

  const invTab = nodes(h.tree, (node) => node.type === 'button')[1];
  invTab.props.onClick();
  await h.flush();

  inventory.resolve({ total_inventory_value: 500000, items: [] });
  await h.flush();
  assert.match(text(h.tree), /۵۰۰,۰۰۰/);

  profitability.reject(new Error('stale tab failure'));
  await h.flush();
  assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);
});

test('ServicesPage uses step="any" price input and decrements page directly after deleting sole item on page > 1', async (t) => {
  const confirmDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'confirm');
  Object.defineProperty(globalThis, 'confirm', { configurable: true, value: () => true });
  t.after(() => {
    if (confirmDescriptor) Object.defineProperty(globalThis, 'confirm', confirmDescriptor);
    else Reflect.deleteProperty(globalThis, 'confirm');
  });

  const requestedPages: number[] = [];
  const deletedIds: number[] = [];
  const h = mountComponent('../src/pages/ServicesPage.tsx', 'ServicesPage', {
    '../api/services': {
      servicesApi: {
        getServices: async (params: any) => {
          requestedPages.push(params.page);
          if (params.page === 2) {
            return page([{ service_id: 99, service_name: 'Wheel Alignment', price: 250000 }], 2, 2);
          }
          return page([{ service_id: 1, service_name: 'Balancing', price: 150000 }], 1, 2);
        },
        deleteService: async (id: number) => {
          deletedIds.push(id);
        },
      },
    },
    '../context/AuthContext': { useAuth: () => ({ user: { id: 1, role: 'MANAGER' }, currencyUnit: 'rial' }) },
    '../utils/formatters': formatters,
    '../utils/errorParser': { parseApiError },
    '../utils/invoiceRequests': { createRequestSequence },
  });
  t.after(() => h.unmount());
  await h.flush();

  find(h.tree, (node) => node.type === 'button' && text(node).includes('تعریف خدمت')).props.onClick();
  h.render();
  assert.equal(find(h.tree, (node) => node.props?.id === 'service-price').props.step, 'any');
  find(h.tree, (node) => node.type === 'button' && text(node) === 'انصراف').props.onClick();
  h.render();

  find(h.tree, (node) => node.type === 'button' && text(node) === 'بعدی').props.onClick();
  h.render();
  await h.flush();
  assert.deepEqual(requestedPages, [1, 2]);

  await find(h.tree, (node) => node.type === 'button' && node.props?.['aria-label'] === 'حذف خدمت').props.onClick();
  h.render();
  await h.flush();
  assert.deepEqual(deletedIds, [99]);
  assert.deepEqual(requestedPages, [1, 2, 1]);
});

test('SuppliersPage decrements page directly after deleting sole item on page > 1', async (t) => {
  const confirmDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'confirm');
  Object.defineProperty(globalThis, 'confirm', { configurable: true, value: () => true });
  t.after(() => {
    if (confirmDescriptor) Object.defineProperty(globalThis, 'confirm', confirmDescriptor);
    else Reflect.deleteProperty(globalThis, 'confirm');
  });

  const requestedPages: number[] = [];
  const deletedIds: number[] = [];
  const h = mountComponent('../src/pages/SuppliersPage.tsx', 'SuppliersPage', {
    '../api/suppliers': {
      suppliersApi: {
        getSuppliers: async (params: any) => {
          requestedPages.push(params.page);
          if (params.page === 2) {
            return page([{ supplier_id: 55, supplier_name: 'Supplier Page 2' }], 2, 2);
          }
          return page([{ supplier_id: 1, supplier_name: 'Supplier Page 1' }], 1, 2);
        },
        deleteSupplier: async (id: number) => {
          deletedIds.push(id);
        },
      },
    },
    '../context/AuthContext': { useAuth: () => ({ user: { id: 1, role: 'MANAGER' }, currencyUnit: 'rial' }) },
    '../utils/errorParser': { parseApiError },
    '../utils/invoiceRequests': { createRequestSequence },
  });
  t.after(() => h.unmount());
  await h.flush();

  find(h.tree, (node) => node.type === 'button' && text(node) === 'بعدی').props.onClick();
  h.render();
  await h.flush();
  assert.deepEqual(requestedPages, [1, 2]);

  await find(h.tree, (node) => node.type === 'button' && node.props?.['aria-label'] === 'حذف تأمین‌کننده').props.onClick();
  h.render();
  await h.flush();
  assert.deepEqual(deletedIds, [55]);
  assert.deepEqual(requestedPages, [1, 2, 1]);
});

test('StockMovements includes SALE_CANCEL filter option and badge', async (t) => {
  const h = mountComponent('../src/pages/StockMovements.tsx', 'StockMovements', {
    '../api/catalog': {
      catalogApi: {
        getStockMovements: async () => page([{
          movement_id: 7,
          tire_name: 'Barez P618',
          brand_name: 'Barez',
          movement_type: 'SALE_CANCEL',
          movement_type_display: 'Canceled Sale',
          quantity: 2,
          balance_after: 10,
          created_at: '2026-11-05T10:00:00Z',
        }]),
      },
    },
    '../context/AuthContext': { useAuth: () => ({ user: { id: 1, role: 'MANAGER' }, currencyUnit: 'rial' }) },
    '../utils/formatters': formatters,
    '../utils/errorParser': { parseApiError },
    '../utils/invoiceRequests': { createRequestSequence },
  });
  t.after(() => h.unmount());
  await h.flush();

  assert.equal(nodes(h.tree, (node) => node.type === 'option' && node.props.value === 'SALE_CANCEL').length, 1);
  assert.match(text(h.tree), /لغو فاکتور فروش/);
});

test('StockAdjustmentModal uses Modal dialog semantics and resets fields when tire prop changes', async (t) => {
  const tireA = { tire_id: 1, tire_name: 'Tire A', brand_name: 'B1', size_name: 'S1', stock_quantity: 5 };
  const tireB = { tire_id: 2, tire_name: 'Tire B', brand_name: 'B2', size_name: 'S2', stock_quantity: 12 };
  const h = mountComponent('../src/components/catalog/StockAdjustmentModal.tsx', 'StockAdjustmentModal', {
    '../../api/catalog': { catalogApi: { adjustStock: async () => ({}) } },
    '../../utils/errorParser': { parseApiError },
  }, { tire: tireA, onClose() {}, onSuccess() {} });
  t.after(() => h.unmount());

  assert.equal(nodes(h.tree, (node) => typeof node.type === 'function' && node.type.name === 'Modal').length, 1);
  const closeBtn = find(h.tree, (node) => node.props?.['aria-label'] === 'بستن پنجره');
  assert.equal(closeBtn.props.type, 'button');

  find(h.tree, (node) => node.type === 'input' && node.props.type === 'number').props.onChange({ target: { value: '9' } });
  find(h.tree, (node) => node.type === 'textarea').props.onChange({ target: { value: '   ' } });
  h.render();
  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.match(text(h.tree), /ثبت دلیل یا شرح انبارگردانی الزامی است/);

  h.render({ tire: tireB, onClose() {}, onSuccess() {} });
  await h.flush();
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.type === 'number').props.value, 12);
  assert.equal(find(h.tree, (node) => node.type === 'textarea').props.value, '');
  assert.ok(!text(h.tree).includes('ثبت دلیل یا شرح انبارگردانی الزامی است'));
});
