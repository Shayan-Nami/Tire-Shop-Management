import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import { AxiosError } from 'axios';
import * as formatters from '../src/utils/formatters.ts';
import { parseApiError } from '../src/utils/errorParser.ts';
import * as invoiceRequests from '../src/utils/invoiceRequests.ts';
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
    '../utils/invoiceRequests': invoiceRequests,
    '../../utils/invoiceRequests': invoiceRequests,
    '../components/finance/PaymentModal': { PaymentModal: 'payment-modal' },
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
    if (kind === 'return') {
      change(h, find(h, (node) => node.type === 'textarea' && node.props.id === 'sales-return-reason'), 'تست علت مرجوعی');
    }
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

test('SalesReturnModal rejects blank reason and sends auto_refund, payment_method, and reference_number', async (t) => {
  const sent: any[] = [];
  const invoice = {
    sales_invoice_id: 11,
    invoice_number: 'S-11',
    customer_name: 'Customer',
    total_amount: '1000.00',
    net_amount: '1000.00',
    remaining_amount: '0.00',
    tire_items: [{ id: 10, tire: 1, tire_name: 'Tire', quantity: 4, unit_price: '250.00' }],
  };
  const h = mountComponent('../src/components/invoices/SalesReturnModal.tsx', 'SalesReturnModal', {
    '../../api/invoices': {
      invoicesApi: {
        createSalesReturn: async (payload: any) => {
          sent.push(payload);
          return payload;
        },
      },
    },
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../../utils/formatters': formatters,
    '../../utils/errorParser': { parseApiError },
    '../../utils/invoiceRequests': invoiceRequests,
  }, { invoice, onClose() {}, onSuccess() {} });
  t.after(() => h.unmount());
  await h.flush();

  change(h, find(h, (node) => node.type === 'input' && node.props.type === 'number'), '1');
  change(h, find(h, (node) => node.type === 'textarea' && node.props.id === 'sales-return-reason'), '   ');
  await find(h, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();

  assert.equal(sent.length, 0);
  assert.match(text(find(h, (node) => node.props?.role === 'alert')), /ثبت علت مرجوعی کالا الزامی است/);

  change(h, find(h, (node) => node.type === 'textarea' && node.props.id === 'sales-return-reason'), 'عدم تطابق سایز');
  change(h, find(h, (node) => node.type === 'select' && node.props.id === 'sales-return-payment-method'), 'CARD_TO_CARD');
  change(h, find(h, (node) => node.type === 'input' && node.props.id === 'sales-return-reference'), 'REF-55');
  await find(h, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();

  assert.deepEqual(sent, [{
    sales_invoice: 11,
    items: [{ sales_invoice_tire_item_id: 10, quantity: 1 }],
    reason: 'عدم تطابق سایز',
    auto_refund: true,
    payment_method: 'CARD_TO_CARD',
    reference_number: 'REF-55',
  }]);
});

test('PurchaseInvoices retries selector loading when initial fetch fails', async (t) => {
  let failSelectors = true;
  const h = mountComponent('../src/pages/PurchaseInvoices.tsx', 'PurchaseInvoices', {
    '../api/invoices': { invoicesApi: { getPurchaseInvoices: async () => page([]) } },
    '../api/catalog': { catalogApi: { getTires: async () => {
      if (failSelectors) throw new Error('selectors down');
      return page([{ tire_id: 1, tire_name: 'Tire', sale_price: '100' }]);
    } } },
    '../api/suppliers': { suppliersApi: { getSuppliers: async () => page([{ supplier_id: 1, supplier_name: 'Supplier' }]) } },
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { role: 'MANAGER' } }) },
    '../utils/formatters': formatters,
    '../utils/errorParser': { parseApiError },
    '../utils/invoiceRequests': invoiceRequests,
    '../components/finance/PaymentModal': { PaymentModal: 'payment-modal' },
  });
  t.after(() => h.unmount());
  await h.flush();

  const alert = find(h, (node) => node.props?.role === 'alert');
  assert.match(text(alert), /selectors down/);
  failSelectors = false;
  const retryButton = nodes(alert, (node) => node.type === 'button' && text(node) === 'تلاش مجدد')[0];
  assert.ok(retryButton, 'Expected retry button inside selector error alert');
  retryButton.props.onClick();
  h.render();
  await h.flush();

  assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);
  const createBtn = find(h, (node) => node.type === 'button' && text(node).includes('ثبت فاکتور خرید (ورود کالا)'));
  assert.equal(createBtn.props.disabled, false);
});

test('PaymentModal and CustomerRefundModal truncate default amounts and enforce single-flight submission', async (t) => {
  const paymentCalls: any[] = [];
  const pendingPayment = deferred<any>();
  const purchaseInvoice = {
    purchase_invoice_id: 9,
    invoice_number: 'P-1405-00009',
    invoice_date: '2026-11-01T10:00:00Z',
    supplier: 3,
    supplier_name: 'تأمین‌کننده تست',
    status: 'CONFIRMED',
    payment_status: 'PARTIAL',
    total_amount: '5000.00',
    remaining_amount: '1234.569',
    tire_items: [],
  };

  const pModal = mountComponent('../src/components/finance/PaymentModal.tsx', 'PaymentModal', {
    '../../api/finance': { financeApi: { createPayment: (payload: any) => { paymentCalls.push(payload); return pendingPayment.promise; } } },
    '../../api/invoices': { invoicesApi: { getPurchaseInvoices: async () => page([]) } },
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../../utils/formatters': formatters,
    '../../utils/errorParser': { parseApiError },
    '../../utils/invoiceRequests': invoiceRequests,
  }, { isOpen: true, purchaseInvoice, onClose() {}, onSuccess() {} });
  t.after(() => pModal.unmount());
  await pModal.flush();

  assert.equal(find(pModal, (node) => node.props?.id === 'payment-amount').props.value, '1234.56');
  change(pModal, find(pModal, (node) => node.props?.id === 'payment-reference'), 'PAY-10');
  const pSubmit = () => find(pModal, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  const p1 = pSubmit();
  const p2 = pSubmit();
  await pModal.flush();
  assert.equal(paymentCalls.length, 1);
  pendingPayment.resolve({});
  await Promise.all([p1, p2]);
  assert.deepEqual(paymentCalls[0], {
    purchase_invoice: 9,
    amount: 1234.56,
    payment_method: 'BANK_TRANSFER',
    reference_number: 'PAY-10',
    notes: undefined,
  });

  const refundCalls: any[] = [];
  const salesInvoiceWithExcess = {
    sales_invoice_id: 14,
    invoice_number: 'S-1405-00014',
    customer_name: 'مشتری مازاد',
    status: 'CONFIRMED',
    payment_status: 'PAID',
    total_amount: '1000.00',
    excess_amount: '321.987',
  };
  const rModal = mountComponent('../src/components/finance/CustomerRefundModal.tsx', 'CustomerRefundModal', {
    '../../api/finance': { financeApi: { createCustomerRefund: async (payload: any) => { refundCalls.push(payload); return payload; } } },
    '../../api/invoices': { invoicesApi: { getSalesInvoices: async () => page([salesInvoiceWithExcess]) } },
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../../utils/formatters': formatters,
    '../../utils/errorParser': { parseApiError },
    '../../utils/invoiceRequests': invoiceRequests,
  }, { isOpen: true, onClose() {}, onSuccess() {} });
  t.after(() => rModal.unmount());
  await rModal.flush();

  change(rModal, find(rModal, (node) => node.props?.id === 'refund-sales-invoice'), '14');
  assert.equal(find(rModal, (node) => node.props?.id === 'refund-amount').props.value, '321.98');
  await find(rModal, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await rModal.flush();
  assert.deepEqual(refundCalls, [{
    sales_invoice: 14,
    amount: 321.98,
    payment_method: 'POS',
    reference_number: undefined,
    notes: undefined,
  }]);
});

test('PurchaseInvoices allows step="any" cost, keeps empty quantity draft until blur, and blocks modal close while busy', async (t) => {
  const pending = deferred<any>();
  const calls: any[] = [];
  const { h, submit, alerts } = await setup(t, 'purchase', (payload) => {
    calls.push(payload);
    return pending.promise;
  });

  const modal = () => find(h, (node) => typeof node.type === 'function' && node.type.name === 'Modal');
  assert.equal(modal().props.busy, false);

  const qtyInput = () => find(h, (node) => node.props?.['aria-label'] === 'تعداد (حلقه)');
  const costInput = find(h, (node) => node.props?.['aria-label'] === 'نرخ خرید واحد (ریال)');
  assert.equal(costInput.props.step, 'any');

  change(h, qtyInput(), '');
  assert.equal(qtyInput().props.value, '');

  await submit();
  assert.equal(calls.length, 0);
  assert.match(alerts.join(''), /حداقل ۱ حلقه/);

  qtyInput().props.onBlur();
  h.render();
  assert.equal(qtyInput().props.value, '1');

  const submitPromise = submit();
  await h.flush();
  assert.equal(modal().props.busy, true);
  assert.equal(find(h, (node) => node.props?.['aria-label'] === 'بستن پنجره').props.disabled, true);
  assert.equal(find(h, (node) => node.type === 'button' && text(node) === 'انصراف').props.disabled, true);

  pending.resolve({});
  await submitPromise;
  await h.flush();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].tire_items[0].quantity, 1);
});

test('ReceiptModal supports BANK_TRANSFER and both ReceiptModal and SalesReturnModal disable close buttons while busy', async (t) => {
  const pendingReceipt = deferred<any>();
  const sentReceipts: any[] = [];
  const receipt = await setup(t, 'receipt', (payload) => {
    sentReceipts.push(payload);
    return pendingReceipt.promise;
  });

  const methodSelect = find(receipt.h, (node) => node.props?.id === 'receipt-method');
  assert.ok(nodes(methodSelect, (node) => node.type === 'option' && node.props.value === 'BANK_TRANSFER').length === 1);
  change(receipt.h, methodSelect, 'BANK_TRANSFER');

  const receiptSubmit = receipt.submit();
  await receipt.h.flush();
  assert.equal(find(receipt.h, (node) => typeof node.type === 'function' && node.type.name === 'Modal').props.busy, true);
  assert.equal(find(receipt.h, (node) => node.props?.['aria-label'] === 'بستن').props.disabled, true);
  assert.equal(find(receipt.h, (node) => node.type === 'button' && text(node) === 'انصراف').props.disabled, true);

  pendingReceipt.resolve({});
  await receiptSubmit;
  await receipt.h.flush();
  assert.equal(sentReceipts[0].payment_method, 'BANK_TRANSFER');

  const pendingReturn = deferred<any>();
  const ret = await setup(t, 'return', () => pendingReturn.promise);
  const retSubmit = ret.submit();
  await ret.h.flush();
  assert.equal(find(ret.h, (node) => typeof node.type === 'function' && node.type.name === 'Modal').props.busy, true);
  assert.equal(find(ret.h, (node) => node.props?.['aria-label'] === 'بستن').props.disabled, true);
  assert.equal(find(ret.h, (node) => node.type === 'button' && text(node) === 'انصراف').props.disabled, true);

  pendingReturn.resolve({});
  await retSubmit;
  await ret.h.flush();
});

test('PaymentModal and CustomerRefundModal request page_size=100 for fallback invoice selectors', async (t) => {
  const purchaseQueries: any[] = [];
  const salesQueries: any[] = [];

  const pModal = mountComponent('../src/components/finance/PaymentModal.tsx', 'PaymentModal', {
    '../../api/finance': { financeApi: { createPayment: async () => ({}) } },
    '../../api/invoices': {
      invoicesApi: {
        getPurchaseInvoices: async (params: any) => {
          purchaseQueries.push(params);
          return page([]);
        },
      },
    },
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../../utils/formatters': formatters,
    '../../utils/errorParser': { parseApiError },
    '../../utils/invoiceRequests': invoiceRequests,
  }, { isOpen: true, purchaseInvoice: null, onClose() {}, onSuccess() {} });
  t.after(() => pModal.unmount());
  await pModal.flush();
  assert.equal(purchaseQueries[0]?.page_size, 100);

  const rModal = mountComponent('../src/components/finance/CustomerRefundModal.tsx', 'CustomerRefundModal', {
    '../../api/finance': { financeApi: { createCustomerRefund: async () => ({}) } },
    '../../api/invoices': {
      invoicesApi: {
        getSalesInvoices: async (params: any) => {
          salesQueries.push(params);
          return page([]);
        },
      },
    },
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../../utils/formatters': formatters,
    '../../utils/errorParser': { parseApiError },
    '../../utils/invoiceRequests': invoiceRequests,
  }, { isOpen: true, onClose() {}, onSuccess() {} });
  t.after(() => rModal.unmount());
  await rModal.flush();
  assert.equal(salesQueries[0]?.page_size, 100);
});
