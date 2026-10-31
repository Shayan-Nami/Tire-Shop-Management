import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import { AxiosError } from 'axios';
import * as formatters from '../src/utils/formatters.ts';
import { parseApiError } from '../src/utils/errorParser.ts';
import { mountComponent, nodes, page, text } from './componentHarness.ts';

function backendFailure(field: string) {
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, {
    status: 400, statusText: 'Bad Request', headers: {}, config: {} as any,
    data: { success: false, status_code: 400, errors: { [field]: ['Specific backend validation message'] } },
  });
}
function browserAlerts(t: TestContext) {
  const alerts: string[] = [];
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'alert');
  Object.defineProperty(globalThis, 'alert', { configurable: true, value: (message: string) => alerts.push(message) });
  t.after(() => {
    if (descriptor) Object.defineProperty(globalThis, 'alert', descriptor);
    else Reflect.deleteProperty(globalThis, 'alert');
  });
  return alerts;
}

for (const name of ['Customers', 'UsersPage', 'ServicesPage', 'SuppliersPage']) {
  test(`${name} displays wrapped field validation rather than a generic form error`, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] });
    const alerts = browserAlerts(t);
    const reject = async () => { throw backendFailure(name === 'UsersPage' ? 'role' : 'national_code'); };
    const h = mountComponent(`../src/pages/${name}.tsx`, name, {
      '../api/crm': { crmApi: { getCustomers: async () => page([]), createCustomer: reject } },
      '../api/auth': { authApi: { getUsers: async () => [], createUser: reject } },
      '../api/services': { servicesApi: { getServices: async () => page([]), createService: reject } },
      '../api/suppliers': { suppliersApi: { getSuppliers: async () => page([]), createSupplier: reject } },
      '../context/AuthContext': { useAuth: () => ({ user: { id: 1, role: 'MANAGER' }, currencyUnit: 'rial' }) },
      '../components/plates/IranianPlateBadge': { IranianPlateBadge: 'plate-badge' },
      '../utils/formatters': formatters,
      '../utils/errorParser': { parseApiError },
    });
    t.after(() => h.unmount());
    await h.flush();
    const add = nodes(h.tree, (node) => node.type === 'button')[0];
    assert.ok(add);
    add.props.onClick();
    h.render();
    if (name === 'UsersPage') {
      const password = nodes(h.tree, (node) => node.type === 'input' && node.props.type === 'password')[0];
      password.props.onChange({ target: { value: 'Valid-password-123' } });
      h.render();
    }
    const form = nodes(h.tree, (node) => node.type === 'form')[0];
    assert.ok(form);
    await form.props.onSubmit({ preventDefault() {} });
    await h.flush();
    assert.ok((name === 'UsersPage' ? text(h.tree) : alerts.join('')).includes('Specific backend validation message'));
    assert.ok(nodes(h.tree, (node) => node.type === 'form').length, 'Rejected form must remain open');
  });
}

for (const name of ['StockAdjustmentModal', 'CancelVoucherModal']) {
  test(`${name} displays wrapped reason validation`, async (t) => {
    const h = mountComponent(`../src/components/${name === 'StockAdjustmentModal' ? 'catalog' : 'finance'}/${name}.tsx`, name, {
      '../../api/catalog': { catalogApi: { adjustStock: async () => { throw backendFailure('reason'); } } },
      '../../utils/errorParser': { parseApiError },
    }, {
      isOpen: true, title: 'Cancel voucher', tire: { tire_id: 1, tire_name: 'Tire', stock_quantity: 5 },
      onConfirm: async () => { throw backendFailure('reason'); }, onSuccess() {}, onClose() {},
    });
    t.after(() => h.unmount());
    nodes(h.tree, (node) => node.type === 'textarea')[0].props.onChange({ target: { value: 'Correction' } });
    h.render();
    await nodes(h.tree, (node) => node.type === 'form')[0].props.onSubmit({ preventDefault() {} });
    await h.flush();
    assert.ok(text(h.tree).includes('Specific backend validation message'));
  });
}
