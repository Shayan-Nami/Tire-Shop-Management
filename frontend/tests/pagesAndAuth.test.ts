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

function setupBrowserGlobals(t: TestContext, initialStorage: Record<string, string> = {}) {
  const values = new Map<string, string>(Object.entries(initialStorage));
  const listeners = new Map<string, Set<(event: any) => void>>();
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
  const win = {
    location: { href: '/', search: '' },
    addEventListener(type: string, fn: (event: any) => void) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(fn);
    },
    removeEventListener(type: string, fn: (event: any) => void) {
      listeners.get(type)?.delete(fn);
    },
    dispatchStorage(event: { key: string | null; newValue?: string | null }) {
      for (const fn of listeners.get('storage') ?? []) fn(event);
    },
  };
  const descriptors = ['localStorage', 'window'].map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: win });
  t.after(() => {
    for (const [name, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  });
  return { values, win };
}

test('AuthContext syncs user and currency across tabs via storage events', async (t) => {
  const { win } = setupBrowserGlobals(t, {
    access_token: 'tok-1',
    refresh_token: 'ref-1',
    user_info: JSON.stringify({ id: 1, username: 'ali', role: 'MANAGER' }),
    preferred_currency: 'toman',
  });
  const { clearLocalSession } = loadComponent('../src/utils/session.ts', {
    '../api/client': { apiClient: { defaults: { headers: { common: {} } } } },
  });
  const h = mountComponent('../src/context/AuthContext.tsx', 'AuthProvider', {
    '../api/auth': { authApi: { getCurrentUser: async () => ({ id: 1, username: 'ali', role: 'MANAGER' }) } },
    '../utils/session': { clearLocalSession },
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

  win.dispatchStorage({ key: 'access_token', newValue: null });
  await h.flush();
  assert.equal(h.tree.props.value.user, null);
  assert.equal(h.tree.props.value.isAuthenticated, false);
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
