import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import * as requests from '../src/utils/invoiceRequests.ts';
import * as formatters from '../src/utils/formatters.ts';
import { parseApiError } from '../src/utils/errorParser.ts';
import { deferred, mountComponent, nodes, page, text } from './componentHarness.ts';

const customer = (id: number) => ({ customer_id: id, full_name: `Customer ${id}`, phone_number: `0912000000${id}` });
const vehicle = (id: number, owner = id) => ({ vehicle_id: id, customer: owner, model: `Car ${id}`, license_plate: '12ب345-ایران11' });
const tire = (id: number) => ({ tire_id: id, tire_name: `Tire ${id}`, sale_price: 100, stock_quantity: 10 });
const service = (id: number) => ({ service_id: id, service_name: `Service ${id}`, price: 10 });
type Harness = ReturnType<typeof mountComponent>;

function find(h: Harness, predicate: (node: any) => boolean) {
  const result = nodes(h.tree, predicate)[0];
  assert.ok(result, 'Expected component control was not found');
  return result;
}
const byId = (h: Harness, id: string) => find(h, (node) => node.props?.id === id);
const button = (h: Harness, label: string) => find(h, (node) => node.type === 'button' && text(node) === label);
function change(h: Harness, id: string, value: string) {
  byId(h, id).props.onChange({ target: { value } });
  h.render();
}
function changeLabel(h: Harness, label: string, value: string) {
  find(h, (node) => node.props?.['aria-label'] === label).props.onChange({ target: { value } });
  h.render();
}
const submit = (h: Harness) => find(h, (node) => node.props?.['aria-describedby'] === 'invoice-submit-help');
const options = (h: Harness, id: string) => nodes(byId(h, id), (node) => node.type === 'option');

function setup(t: TestContext, overrides: Record<string, any> = {}, exportName = 'CreateInvoice') {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const crm = {
    getCustomers: async () => page([customer(1), customer(2), customer(3)]),
    getVehicles: async ({ customer: owner }: any) => page([vehicle(owner)]),
    createCustomer: async () => customer(4),
    createVehicle: async () => vehicle(4),
    ...overrides.crm,
  };
  const saved: any[] = [];
  const navigation: string[] = [];
  const invoices = {
    createSalesInvoice: async (payload: any) => { saved.push(payload); },
    getSalesInvoices: async () => page([]),
    ...overrides.invoices,
  };
  const h = mountComponent(`../src/pages/${exportName}.tsx`, exportName, {
    'react-router-dom': { useNavigate: () => (url: string) => navigation.push(url), Link: 'a' },
    '../api/crm': { crmApi: crm },
    '../api/catalog': { catalogApi: { getTires: async () => page([tire(1)]), ...overrides.catalog } },
    '../api/services': { servicesApi: { getServices: async () => page([service(1)]), ...overrides.services } },
    '../api/invoices': { invoicesApi: invoices },
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { role: 'MANAGER' } }) },
    '../components/plates/IranianPlateBadge': { IranianPlateBadge: 'plate-badge' },
    '../components/invoices/InvoiceDetailModal': { InvoiceDetailModal: 'invoice-detail' },
    '../components/invoices/SalesReturnModal': { SalesReturnModal: 'sales-return' },
    '../components/finance/ReceiptModal': { ReceiptModal: 'receipt-modal' },
    '../utils/formatters': formatters,
    '../utils/invoiceRequests': requests,
    '../utils/errorParser': { parseApiError },
  });
  t.after(() => h.unmount());
  return { h, crm, saved, navigation, async ready() { t.mock.timers.tick(350); await h.flush(); } };
}

function openQuickCreate(h: Harness) {
  button(h, 'ثبت سریع مشتری/خودرو جدید').props.onClick();
  h.render();
  change(h, 'quick-customer-name', 'New customer');
  change(h, 'quick-customer-phone', '09123456789');
  change(h, 'quick-vehicle-plate', '12ب345-ایران11');
}
const quickSubmit = (h: Harness) => find(h, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });

test('customer change clears vehicles immediately and rejects a captured stale submit', async (t) => {
  const pending = deferred<any>();
  const { h, ready, saved } = setup(t, { crm: { getVehicles: ({ customer: owner }: any) => owner === 2 ? pending.promise : Promise.resolve(page([vehicle(owner)])) } });
  await ready();
  change(h, 'invoice-customer', '1');
  await h.flush();
  changeLabel(h, 'افزودن خدمت کارگاهی', '1');
  const staleSubmit = submit(h).props.onClick;
  assert.equal(byId(h, 'invoice-vehicle').props.value, 1);
  change(h, 'invoice-customer', '2');
  assert.equal(byId(h, 'invoice-vehicle').props.value, '');
  assert.equal(options(h, 'invoice-vehicle').length, 1);
  assert.equal(submit(h).props.disabled, true);
  await staleSubmit();
  assert.equal(saved.length, 0);
  pending.resolve(page([vehicle(2)]));
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props.value, 2);
  await submit(h).props.onClick();
  assert.equal(saved[0].customer, 2);
  assert.equal(saved[0].vehicle, 2);
});

test('superseded vehicle error and finally cannot clear the newer loading state', async (t) => {
  const old = deferred<any>();
  const latest = deferred<any>();
  const { h, ready } = setup(t, { crm: { getVehicles: ({ customer: owner }: any) => owner === 1 ? old.promise : latest.promise } });
  await ready();
  change(h, 'invoice-customer', '1');
  change(h, 'invoice-customer', '2');
  old.reject(new Error('obsolete vehicle error'));
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props['aria-busy'], true);
  assert.ok(!text(h.tree).includes('obsolete vehicle error'));
  latest.resolve(page([vehicle(2)]));
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props.value, 2);
});

test('late vehicle success cannot restore a cleared customer selection', async (t) => {
  const pending = deferred<any>();
  const { h, ready } = setup(t, { crm: { getVehicles: () => pending.promise } });
  await ready();
  change(h, 'invoice-customer', '1');
  change(h, 'invoice-customer', '');
  pending.resolve(page([vehicle(1)]));
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props.value, '');
  assert.equal(submit(h).props.disabled, true);
});

test('vehicle loading failure is visible, and foreign vehicles cannot be submitted', async (t) => {
  let fail = true;
  const { h, ready, saved } = setup(t, { crm: { getVehicles: async () => {
    if (fail) throw new Error('vehicles unavailable');
    return page([vehicle(9, 3)]);
  } } });
  await ready();
  change(h, 'invoice-customer', '1');
  await h.flush();
  assert.match(text(h.tree), /vehicles unavailable/);
  fail = false;
  change(h, 'invoice-customer', '2');
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props.value, '');
  change(h, 'invoice-vehicle', '9');
  await submit(h).props.onClick();
  assert.equal(saved.length, 0);
});

test('every invoice selector exposes records beyond page one', async (t) => {
  const calls: Record<string, number[]> = { customers: [], vehicles: [], tires: [], services: [] };
  const paged = (kind: string, make: (id: number) => any) => async ({ page: number }: any) => {
    calls[kind].push(number);
    return page(Array.from({ length: 60 }, (_, i) => make((number - 1) * 60 + i + 1)), number, 3);
  };
  const { h, ready } = setup(t, {
    crm: { getCustomers: paged('customers', customer), getVehicles: paged('vehicles', (id) => vehicle(id, 1)) },
    catalog: { getTires: paged('tires', tire) },
    services: { getServices: paged('services', service) },
  });
  await ready();
  change(h, 'invoice-customer', '1');
  await h.flush();
  assert.equal(options(h, 'invoice-customer').length, 181);
  assert.equal(options(h, 'invoice-vehicle').length, 180);
  for (const label of ['افزودن تایر از کاتالوگ', 'افزودن خدمت کارگاهی']) {
    const control = find(h, (node) => node.props?.['aria-label'] === label);
    assert.equal(nodes(control, (node) => node.type === 'option').length, 181);
  }
  for (const call of Object.values(calls)) assert.deepEqual(call, [1, 2, 3]);
});

test('superseded customer searches ignore stale responses, errors and finalizers', async (t) => {
  const old = deferred<any>();
  const latest = deferred<any>();
  const { h, ready } = setup(t, { crm: { getCustomers: ({ search }: any) => search === 'old' ? old.promise : search === 'new' ? latest.promise : Promise.resolve(page([customer(1)])) } });
  await ready();
  change(h, 'invoice-customer', '1');
  await h.flush();
  changeLabel(h, 'جستجوی نام یا موبایل مشتری', 'old');
  t.mock.timers.tick(350);
  await h.flush();
  changeLabel(h, 'جستجوی نام یا موبایل مشتری', 'new');
  t.mock.timers.tick(350);
  await h.flush();
  old.reject(new Error('obsolete search'));
  await h.flush();
  assert.equal(byId(h, 'invoice-customer').props['aria-busy'], true);
  latest.resolve(page([customer(3)]));
  await h.flush();
  assert.deepEqual(options(h, 'invoice-customer').slice(1).map((node) => node.props.value), [1, 3]);
  assert.ok(!text(h.tree).includes('obsolete search'));
});

test('quick creation is single-flight and invalidates old vehicle responses', async (t) => {
  const oldVehicles = deferred<any>();
  const createdCustomer = deferred<any>();
  let customerPosts = 0;
  const { h, ready } = setup(t, { crm: {
    getVehicles: ({ customer: owner }: any) => owner === 1 ? oldVehicles.promise : Promise.resolve(page([vehicle(40, 4)])),
    createCustomer: () => { customerPosts++; return createdCustomer.promise; },
  } });
  await ready();
  change(h, 'invoice-customer', '1');
  openQuickCreate(h);
  const send = quickSubmit(h);
  const duplicate = quickSubmit(h);
  h.render();
  assert.equal(customerPosts, 1);
  assert.equal(submit(h).props.disabled, true);
  oldVehicles.resolve(page([vehicle(1)]));
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props.value, '');
  createdCustomer.resolve(customer(4));
  await Promise.all([send, duplicate]);
  await h.flush();
  assert.equal(byId(h, 'invoice-customer').props.value, 4);
  assert.equal(byId(h, 'invoice-vehicle').props.value, 4);
  assert.deepEqual(options(h, 'invoice-vehicle').map((node) => node.props.value), [4, 40]);
  assert.equal(nodes(h.tree, (node) => node.type === 'dialog').length, 0);
});

test('closing quick-create before customer response prevents selection and vehicle POST', async (t) => {
  const pending = deferred<any>();
  let vehiclePosts = 0;
  const { h, ready } = setup(t, { crm: {
    createCustomer: () => pending.promise,
    createVehicle: async () => { vehiclePosts++; return vehicle(4); },
  } });
  await ready();
  openQuickCreate(h);
  const sending = quickSubmit(h);
  h.render();
  find(h, (node) => node.props?.['aria-label'] === 'بستن ثبت سریع').props.onClick();
  h.render();
  pending.resolve(customer(4));
  await sending;
  await h.flush();
  assert.equal(vehiclePosts, 0);
  assert.equal(byId(h, 'invoice-customer').props.value, '');
});

test('a superseded quick-create vehicle response cannot overwrite another customer', async (t) => {
  const pending = deferred<any>();
  const { h, ready } = setup(t, { crm: { createVehicle: () => pending.promise } });
  await ready();
  openQuickCreate(h);
  const sending = quickSubmit(h);
  await h.flush();
  find(h, (node) => node.props?.['aria-label'] === 'بستن ثبت سریع').props.onClick();
  h.render();
  change(h, 'invoice-customer', '2');
  await h.flush();
  pending.resolve(vehicle(4));
  await sending;
  await h.flush();
  assert.equal(byId(h, 'invoice-customer').props.value, 2);
  assert.equal(byId(h, 'invoice-vehicle').props.value, 2);
});

test('retry after vehicle failure reuses the created customer', async (t) => {
  let customerPosts = 0;
  let vehiclePosts = 0;
  const { h, ready } = setup(t, { crm: {
    createCustomer: async () => { customerPosts++; return customer(4); },
    createVehicle: async () => { if (++vehiclePosts === 1) throw new Error('invalid plate'); return vehicle(4); },
  } });
  await ready();
  openQuickCreate(h);
  await quickSubmit(h);
  await h.flush();
  assert.match(text(h.tree), /invalid plate/);
  assert.equal(byId(h, 'invoice-vehicle').props.value, '');
  await quickSubmit(h);
  await h.flush();
  assert.equal(customerPosts, 1);
  assert.equal(vehiclePosts, 2);
  assert.equal(byId(h, 'invoice-vehicle').props.value, 4);
});

test('draft submit sends DRAFT, with duplicate submission blocked', async (t) => {
  const pending = deferred<any>();
  let posts = 0;
  const { h, ready } = setup(t, { invoices: { createSalesInvoice: async (payload: any) => {
    posts++;
    assert.equal(payload.status, 'DRAFT');
    await pending.promise;
  } } });
  await ready();
  change(h, 'invoice-customer', '1');
  await h.flush();
  changeLabel(h, 'افزودن خدمت کارگاهی', '1');
  button(h, 'پیش‌نویس').props.onClick();
  h.render();
  assert.match(text(submit(h)), /ذخیره پیش‌نویس/);
  const handler = submit(h).props.onClick;
  const first = handler();
  const second = handler();
  assert.equal(posts, 1);
  pending.resolve(undefined);
  await Promise.all([first, second]);
});

test('catalog and customer failures are visible rather than empty-success states', async (t) => {
  const { h, ready } = setup(t, {
    catalog: { getTires: async () => { throw new Error('catalog offline'); } },
    crm: { getCustomers: async () => { throw new Error('customers offline'); } },
  });
  await ready();
  const alerts = nodes(h.tree, (node) => node.props?.role === 'alert').map(text).join(' ');
  assert.match(alerts, /catalog offline/);
  assert.match(alerts, /customers offline/);
});

test('sales list keeps the newest search response and ignores stale failures', async (t) => {
  const old = deferred<any>();
  const latest = deferred<any>();
  const { h } = setup(t, { invoices: { getSalesInvoices: ({ search }: any) => search ? latest.promise : old.promise } }, 'SalesInvoices');
  await h.flush();
  changeLabel(h, 'جستجوی فاکتور فروش', 'new');
  await h.flush();
  old.reject(new Error('obsolete invoice error'));
  await h.flush();
  assert.match(text(h.tree), /در حال دریافت فاکتورها/);
  latest.resolve(page([{ sales_invoice_id: 2, invoice_number: 'NEWEST', status: 'DRAFT', net_amount: 1 }]));
  await h.flush();
  assert.match(text(h.tree), /NEWEST/);
  assert.ok(!text(h.tree).includes('obsolete invoice error'));
});

test('late vehicle success cannot overwrite a newer completed customer selection', async (t) => {
  const pending = deferred<any>();
  const { h, ready } = setup(t, { crm: { getVehicles: ({ customer: owner }: any) => owner === 1 ? pending.promise : Promise.resolve(page([vehicle(owner)])) } });
  await ready();
  change(h, 'invoice-customer', '1');
  change(h, 'invoice-customer', '2');
  await h.flush();
  pending.resolve(page([vehicle(1)]));
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props.value, 2);
  assert.deepEqual(options(h, 'invoice-vehicle').map((node) => node.props.value), [2]);
});

test('late customer search success cannot overwrite newer results', async (t) => {
  const pending = deferred<any>();
  const { h, ready } = setup(t, { crm: { getCustomers: ({ search }: any) => search === 'old' ? pending.promise : Promise.resolve(page([customer(search ? 3 : 1)])) } });
  await ready();
  changeLabel(h, 'جستجوی نام یا موبایل مشتری', 'old');
  t.mock.timers.tick(350);
  await h.flush();
  changeLabel(h, 'جستجوی نام یا موبایل مشتری', 'new');
  t.mock.timers.tick(350);
  await h.flush();
  pending.resolve(page([customer(2)]));
  await h.flush();
  assert.deepEqual(options(h, 'invoice-customer').slice(1).map((node) => node.props.value), [3]);
});

test('unmount invalidates pending catalog, customer, vehicle and quick-create operations', async (t) => {
  const pendingCatalog = deferred<any>();
  const pendingCustomers = deferred<any>();
  const pendingVehicles = deferred<any>();
  const pendingCreation = deferred<any>();
  const { h, ready } = setup(t, {
    catalog: { getTires: () => pendingCatalog.promise },
    crm: {
      getCustomers: () => pendingCustomers.promise,
      getVehicles: () => pendingVehicles.promise,
      createCustomer: () => pendingCreation.promise,
    },
  });
  await ready();
  change(h, 'invoice-customer', '1');
  openQuickCreate(h);
  const sending = quickSubmit(h);
  await h.flush();
  h.unmount();
  pendingCatalog.resolve(page([tire(1)]));
  pendingCustomers.resolve(page([customer(1)]));
  pendingVehicles.resolve(page([vehicle(1)]));
  pendingCreation.resolve(customer(4));
  await sending;
  // The harness throws on any state setter after unmount.
  await h.flush();
});

test('sales list ignores an older successful response after a newer response', async (t) => {
  const pending = deferred<any>();
  const { h } = setup(t, { invoices: { getSalesInvoices: ({ status }: any) => status ? Promise.resolve(page([{ sales_invoice_id: 2, invoice_number: 'NEWEST', status: 'DRAFT' }])) : pending.promise } }, 'SalesInvoices');
  changeLabel(h, 'وضعیت فاکتور', 'DRAFT');
  await h.flush();
  pending.resolve(page([{ sales_invoice_id: 1, invoice_number: 'OBSOLETE', status: 'CONFIRMED' }]));
  await h.flush();
  assert.match(text(h.tree), /NEWEST/);
  assert.ok(!text(h.tree).includes('OBSOLETE'));
});

test('a stale quick-create finalizer cannot release a newer creation lock', async (t) => {
  const old = deferred<any>();
  const latest = deferred<any>();
  let posts = 0;
  const { h, ready } = setup(t, { crm: { createCustomer: () => ++posts === 1 ? old.promise : latest.promise } });
  await ready();
  openQuickCreate(h);
  const first = quickSubmit(h);
  find(h, (node) => node.props?.['aria-label'] === 'بستن ثبت سریع').props.onClick();
  h.render();
  openQuickCreate(h);
  const second = quickSubmit(h);
  old.reject(new Error('obsolete creation error'));
  await first;
  await h.flush();
  assert.equal(button(h, 'در حال ثبت...').props.disabled, true);
  await quickSubmit(h);
  assert.equal(posts, 2);
  assert.ok(!text(h.tree).includes('obsolete creation error'));
  latest.resolve(customer(4));
  await second;
  await h.flush();
  assert.equal(byId(h, 'invoice-vehicle').props.value, 4);
});

test('sales list failures show an alert and retry control', async (t) => {
  let calls = 0;
  const { h } = setup(t, { invoices: { getSalesInvoices: async () => {
    if (++calls === 1) throw new Error('sales offline');
    return page([]);
  } } }, 'SalesInvoices');
  await h.flush();
  assert.match(text(find(h, (node) => node.props?.role === 'alert')), /sales offline/);
  button(h, 'تلاش مجدد').props.onClick();
  h.render();
  await h.flush();
  assert.equal(calls, 2);
  assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);
});
