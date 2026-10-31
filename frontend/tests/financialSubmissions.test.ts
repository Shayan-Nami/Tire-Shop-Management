import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import { AxiosError } from 'axios';
import * as formatters from '../src/utils/formatters.ts';
import { parseApiError } from '../src/utils/errorParser.ts';
import { deferred, mountComponent, nodes, page, text } from './componentHarness.ts';

type Harness = ReturnType<typeof mountComponent>;
function find(h: Harness, predicate: (node: any) => boolean) {
  const node = nodes(h.tree, predicate)[0];
  assert.ok(node, 'Expected financial form control was not found');
  return node;
}
function change(h: Harness, control: any, value: string) {
  control.props.onChange({ target: { value } });
  h.render();
}

async function setup(t: TestContext, kind: string, create: (payload: any) => Promise<any>) {
  const alerts: string[] = [];
  const alertDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'alert');
  Object.defineProperty(globalThis, 'alert', { configurable: true, value: (message: string) => alerts.push(message) });
  t.after(() => {
    if (alertDescriptor) Object.defineProperty(globalThis, 'alert', alertDescriptor);
    else Reflect.deleteProperty(globalThis, 'alert');
  });
  const invoice = { sales_invoice_id: 1, invoice_number: 'S-1', customer_name: 'Customer',
    total_amount: '1000.00', net_amount: '1000.00', remaining_amount: '1000.00',
    tire_items: [{ id: 10, tire: 1, tire_name: 'Tire', quantity: 4, unit_price: '250.00' }] };
  const tire = { tire_id: 1, tire_name: 'Tire', purchase_price: '100.00', sale_price: '250.00' };
  let successes = 0;
  const purchase = kind === 'purchase';
  const name = purchase ? 'PurchaseInvoices' : kind === 'receipt' ? 'ReceiptModal' : 'SalesReturnModal';
  const path = purchase ? '../src/pages/PurchaseInvoices.tsx' : `../src/components/${kind === 'receipt' ? 'finance' : 'invoices'}/${name}.tsx`;
  const h = mountComponent(path, name, {
    '../api/invoices': { invoicesApi: { getPurchaseInvoices: async () => page([]), createPurchaseInvoice: create } },
    '../api/catalog': { catalogApi: { getTires: async () => page([tire]) } },
    '../api/suppliers': { suppliersApi: { getSuppliers: async () => page([{ supplier_id: 1, supplier_name: 'Supplier' }]) } },
    '../../api/finance': { financeApi: { createReceipt: create } },
    '../../api/invoices': { invoicesApi: { createSalesReturn: create } },
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { role: 'MANAGER' } }) },
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../utils/formatters': formatters,
    '../../utils/formatters': formatters,
    '../utils/errorParser': { parseApiError },
    '../../utils/errorParser': { parseApiError },
  }, { invoice, onClose() {}, onSuccess() { successes++; } });
  t.after(() => h.unmount());
  await h.flush();
  if (purchase) {
    find(h, (node) => node.type === 'button' && text(node) === 'ثبت فاکتور خرید (ورود کالا)' ).props.onClick();
    h.render();
    const selects = nodes(h.tree, (node) => node.type === 'select');
    change(h, selects[0], '1');
    change(h, nodes(h.tree, (node) => node.type === 'select')[1], '1');
  } else {
    change(h, find(h, (node) => node.type === 'input' && node.props.type === 'number'), kind === 'receipt' ? '100' : '1');
  }
  const submit = () => find(h, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  return { h, submit, alerts, successes: () => successes };
}

for (const kind of ['purchase', 'receipt', 'return']) {
  test(`${kind} form sends only one mutation while a submission is pending`, async (t) => {
    const pending = deferred<any>();
    const calls: any[] = [];
    const { h, submit, successes } = await setup(t, kind, (payload) => { calls.push(payload); return pending.promise; });
    const first = submit();
    const duplicate = submit();
    await h.flush();
    assert.equal(calls.length, 1, 'Duplicate submission must not create another financial/stock document');
    assert.equal(find(h, (node) => node.type === 'button' && node.props.type === 'submit').props.disabled, true);
    pending.resolve({});
    await Promise.all([first, duplicate]);
    await h.flush();
    if (kind !== 'purchase') assert.equal(successes(), 1);
  });

  test(`${kind} form displays the wrapped backend validation message`, async (t) => {
    const message = 'Backend validation rejected this document';
    const { h, submit, alerts, successes } = await setup(t, kind, async () => {
      throw new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, {
        status: 400, statusText: 'Bad Request', headers: {}, config: {} as any,
        data: { success: false, status_code: 400, errors: { amount: [message] } },
      });
    });
    await submit();
    await h.flush();
    assert.ok((kind === 'purchase' ? alerts.join('') : text(h.tree)).includes(message));
    assert.equal(successes(), 0);
  });

  test(`${kind} form releases its submission lock after a server rejection`, async (t) => {

    let calls = 0;
    const { h, submit } = await setup(t, kind, async () => { calls++; throw new Error('Rejected by server'); });
    await submit();
    await h.flush();
    await submit();
    await h.flush();
    assert.equal(calls, 2);
    assert.equal(find(h, (node) => node.type === 'button' && node.props.type === 'submit').props.disabled, false);
  });
}
