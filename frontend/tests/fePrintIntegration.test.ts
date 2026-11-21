import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import * as formatters from '../src/utils/formatters.ts';
import { parseApiError } from '../src/utils/errorParser.ts';
import { translateMessage, translatePaymentMethod } from '../src/utils/i18n.ts';
import * as invoiceRequests from '../src/utils/invoiceRequests.ts';
import { mountComponent, nodes, page, text } from './componentHarness.ts';

function find(tree: any, predicate: (node: any) => boolean) {
  const match = nodes(tree, predicate)[0];
  assert.ok(match, 'Expected DOM element or control was not found');
  return match;
}

test('CancelVoucherModal resets reason and error state across close and reopen cycles', async (t) => {
  const onConfirm = async () => {
    throw new Error('Server rejected cancellation');
  };
  const baseProps = {
    title: 'ابطال رسید',
    isOpen: true,
    onClose() {},
    onConfirm,
  };
  const h = mountComponent('../src/components/finance/CancelVoucherModal.tsx', 'CancelVoucherModal', {
    '../../utils/errorParser': { parseApiError },
  }, baseProps);
  t.after(() => h.unmount());

  const reasonBox = find(h.tree, (node) => node.type === 'textarea');
  reasonBox.props.onChange({ target: { value: 'اشتباه در شماره سند' } });
  h.render();
  assert.equal(find(h.tree, (node) => node.type === 'textarea').props.value, 'اشتباه در شماره سند');

  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.ok(find(h.tree, (node) => node.props?.role === 'alert'));

  h.render({ ...baseProps, isOpen: false });
  await h.flush();
  assert.equal(h.tree, null);

  h.render({ ...baseProps, isOpen: true });
  await h.flush();
  assert.equal(find(h.tree, (node) => node.type === 'textarea').props.value, '');
  assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);
});

test('ReceiptModal truncates remaining_amount with floor-to-2-decimals and resets when invoice changes', async (t) => {
  const received: any[] = [];
  let shouldReject = true;
  const makeInvoice = (id: number, remaining: string) => ({
    sales_invoice_id: id,
    invoice_number: `INV-${id}`,
    customer: 1,
    customer_name: 'مشتری نمونه',
    customer_phone: '09120000001',
    vehicle: 1,
    license_plate: '12ب345-ایران11',
    total_amount: remaining,
    discount_amount: '0',
    discount_percent: 0,
    net_amount: remaining,
    paid_amount: '0',
    remaining_amount: remaining,
    status: 'CONFIRMED',
    payment_status: 'UNPAID',
    created_at: '2026-01-01T10:00:00Z',
    tire_items: [],
    service_items: [],
  });

  const baseProps = {
    invoice: makeInvoice(1, '1000.999'),
    onClose() {},
    onSuccess() {},
  };
  const h = mountComponent('../src/components/finance/ReceiptModal.tsx', 'ReceiptModal', {
    '../../api/finance': {
      financeApi: {
        createReceipt: async (payload: any) => {
          if (shouldReject) throw new Error('Receipt rejected');
          received.push(payload);
          return payload;
        },
      },
    },
    '../../utils/formatters': formatters,
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../../utils/errorParser': { parseApiError },
  }, baseProps);
  t.after(() => h.unmount());

  const initialInput = find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-amount');
  assert.equal(initialInput.props.value, '1000.99');
  assert.equal(initialInput.props.min, 0.01);
  assert.equal(initialInput.props.step, 'any');

  find(h.tree, (node) => node.type === 'select' && node.props.id === 'receipt-method').props.onChange({
    target: { value: 'CHEQUE' },
  });
  find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-reference').props.onChange({
    target: { value: 'REF-OLD' },
  });
  h.render();
  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.ok(find(h.tree, (node) => node.props?.role === 'alert'));

  const nextProps = { ...baseProps, invoice: makeInvoice(2, '1234.567') };
  h.render(nextProps);
  await h.flush();
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-amount').props.value, '1234.56');
  assert.equal(find(h.tree, (node) => node.type === 'select' && node.props.id === 'receipt-method').props.value, 'POS');
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-reference').props.value, '');
  assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);

  shouldReject = false;
  find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-amount').props.onChange({
    target: { value: '125.75' },
  });
  find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-reference').props.onChange({
    target: { value: 'REF-9' },
  });
  h.render(nextProps);
  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();

  assert.deepEqual(received, [{
    sales_invoice: 2,
    amount: 125.75,
    payment_method: 'POS',
    reference_number: 'REF-9',
    notes: undefined,
  }]);

  h.render({ ...baseProps, invoice: makeInvoice(3, '5000.00') });
  await h.flush();
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-amount').props.value, '5000');

  for (const [rawRemaining, expectedAmount] of [['19.99', '19.99'], ['1.13', '1.13'], ['19.999', '19.99']] as const) {
    h.render({ ...baseProps, invoice: makeInvoice(4, rawRemaining) });
    await h.flush();
    assert.equal(
      find(h.tree, (node) => node.type === 'input' && node.props.id === 'receipt-amount').props.value,
      expectedAmount,
    );
  }
});

test('CreateInvoice locks payment status to UNPAID for DRAFT invoices and unlocks PAID for CONFIRMED', async (t: TestContext) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const submissions: any[] = [];
  const h = mountComponent('../src/pages/CreateInvoice.tsx', 'CreateInvoice', {
    'react-router-dom': { useNavigate: () => () => {} },
    '../api/crm': {
      crmApi: {
        getCustomers: async () => page([{ customer_id: 1, full_name: 'مشتری یک', phone_number: '09120000001' }]),
        getVehicles: async () => page([{ vehicle_id: 10, customer: 1, car_model: 'پژو ۲۰۶', license_plate: '12ب345-ایران11' }]),
      },
    },
    '../api/catalog': {
      catalogApi: {
        getTires: async () => page([{
          tire_id: 5,
          tire_name: 'تایر ۲۱۵',
          brand_name: 'برند',
          size_name: '215/55R17',
          stock_quantity: 10,
          sale_price: '2000000',
          purchase_price: '1500000',
        }]),
      },
    },
    '../api/services': { servicesApi: { getServices: async () => page([]) } },
    '../api/invoices': {
      invoicesApi: {
        createSalesInvoice: async (payload: any) => {
          submissions.push(payload);
          return payload;
        },
      },
    },
    '../components/plates/IranianPlateBadge': { IranianPlateBadge: 'plate-badge' },
    '../utils/formatters': formatters,
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../utils/errorParser': { parseApiError },
    '../utils/invoiceRequests': invoiceRequests,
  });
  t.after(() => h.unmount());

  t.mock.timers.tick(400);
  await h.flush();

  find(h.tree, (node) => node.type === 'select' && node.props.id === 'invoice-customer').props.onChange({
    target: { value: '1' },
  });
  await h.flush();
  find(h.tree, (node) => node.type === 'select' && node.props['aria-label'] === 'افزودن تایر از کاتالوگ').props.onChange({
    target: { value: '5' },
  });
  h.render();

  const btn = (label: string) =>
    find(h.tree, (node) => node.type === 'button' && text(node).includes(label));

  assert.equal(btn('تایید قطعی (کسر انبار)').props['aria-pressed'], true);
  assert.equal(btn('تسویه کامل نقدی/پوز').props['aria-pressed'], true);
  assert.equal(btn('تسویه کامل نقدی/پوز').props.disabled, false);

  btn('پیش‌نویس').props.onClick();
  h.render();
  await h.flush();

  assert.equal(btn('پیش‌نویس').props['aria-pressed'], true);
  assert.equal(btn('تسویه کامل نقدی/پوز').props.disabled, true);
  assert.equal(btn('تسویه کامل نقدی/پوز').props['aria-pressed'], false);
  assert.equal(btn('نسیه / تسویه بعداً').props['aria-pressed'], true);

  btn('تسویه کامل نقدی/پوز').props.onClick();
  h.render();
  assert.equal(btn('تسویه کامل نقدی/پوز').props['aria-pressed'], false);
  assert.equal(btn('نسیه / تسویه بعداً').props['aria-pressed'], true);

  const submitBtn = () =>
    find(h.tree, (node) => node.type === 'button' && node.props['aria-describedby'] === 'invoice-submit-help');

  await submitBtn().props.onClick();
  await h.flush();
  assert.equal(submissions[0].status, 'DRAFT');
  assert.equal(submissions[0].payment_status, 'UNPAID');

  btn('تایید قطعی (کسر انبار)').props.onClick();
  h.render();
  await h.flush();
  assert.equal(btn('تسویه کامل نقدی/پوز').props.disabled, false);

  btn('تسویه کامل نقدی/پوز').props.onClick();
  h.render();
  await submitBtn().props.onClick();
  await h.flush();
  assert.equal(submissions[1].status, 'CONFIRMED');
  assert.equal(submissions[1].payment_status, 'PAID');
});

test('Treasury translates payment methods cleanly in English and Persian including BANK_TRANSFER and legacy Persian values', async (t) => {
  const sampleReceipts = [
    { receipt_id: 1, customer_name: 'A', amount: '1000', payment_method: 'BANK_TRANSFER', payment_method_display: 'حواله بانکی', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false },
    { receipt_id: 2, customer_name: 'B', amount: '2000', payment_method: 'POS', payment_method_display: 'کارتخوان (POS)', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false },
    { receipt_id: 3, customer_name: 'C', amount: '3000', payment_method: 'CASH', payment_method_display: 'نقدی', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false },
    { receipt_id: 4, customer_name: 'D', amount: '4000', payment_method: 'CARD_TO_CARD', payment_method_display: 'کارت به کارت', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false },
    { receipt_id: 5, customer_name: 'E', amount: '5000', payment_method: 'CHEQUE', payment_method_display: 'چک', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false },
    { receipt_id: 6, customer_name: 'F', amount: '6000', payment_method: '', payment_method_display: 'کارتخوان / نقدی', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false },
    { receipt_id: 7, customer_name: 'G', amount: '7000', payment_method: '', payment_method_display: 'حواله / چک', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false },
  ];

  const mountTreasury = (language: 'fa' | 'en') => {
    const langCtx = {
      language,
      direction: language === 'en' ? 'ltr' : 'rtl',
      isRTL: language === 'fa',
      t: (key: string) => translateMessage(key, language),
    };
    return mountComponent('../src/pages/Treasury.tsx', 'Treasury', {
      '../api/finance': {
        financeApi: {
          getReceipts: async () => page(sampleReceipts),
          getPayments: async () => page([]),
          getCustomerRefunds: async () => page([]),
        },
      },
      '../utils/formatters': formatters,
      '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { id: 1, role: 'MANAGER' } }) },
      '../components/finance/CancelVoucherModal': { CancelVoucherModal: 'cancel-voucher-modal' },
      '../components/finance/PaymentModal': { PaymentModal: 'payment-modal' },
      '../components/finance/CustomerRefundModal': { CustomerRefundModal: 'customer-refund-modal' },
      '../utils/invoiceRequests': invoiceRequests,
      '../utils/errorParser': { parseApiError },
      '../utils/i18n': { translatePaymentMethod },
      '../context/LanguageContext': { useLanguage: () => langCtx },
    });
  };

  const enHarness = mountTreasury('en');
  t.after(() => enHarness.unmount());
  await enHarness.flush();
  const enRendered = text(enHarness.tree);
  assert.ok(!enRendered.includes('BANK_TRANSFER'), 'Raw enum BANK_TRANSFER must be translated in English view');
  for (const label of ['Bank transfer', 'Card terminal', 'Cash', 'Cheque', 'Card terminal / cash', 'Bank transfer / cheque']) {
    assert.ok(enRendered.includes(label), `Missing English payment method translation: ${label}`);
  }

  const faHarness = mountTreasury('fa');
  t.after(() => faHarness.unmount());
  await faHarness.flush();
  const faRendered = text(faHarness.tree);
  for (const label of ['حواله بانکی', 'کارتخوان (POS)', 'نقدی', 'کارت به کارت', 'چک', 'کارتخوان / نقدی', 'حواله / چک']) {
    assert.ok(faRendered.includes(label), `Missing Persian payment method label: ${label}`);
  }

  assert.equal(translatePaymentMethod('BANK_TRANSFER', undefined, 'en'), 'Bank transfer');
  assert.equal(translatePaymentMethod('BANK_TRANSFER', undefined, 'fa'), 'انتقال بانکی / حواله');
  assert.equal(translatePaymentMethod('CHECK', undefined, 'en'), 'Cheque');
  assert.equal(translatePaymentMethod(undefined, 'حواله / چک', 'en'), 'Bank transfer / cheque');
  assert.equal(translatePaymentMethod(null, null, 'en'), '-');
});

test('InvoiceDetailModal allows DRAFT confirmation only for MANAGER and TECHNICIAN roles', (t) => {
  const draftInvoice = {
    sales_invoice_id: 1,
    invoice_number: 'S-100',
    customer: 1,
    customer_name: 'مشتری تست',
    customer_phone: '09120000001',
    vehicle: 1,
    license_plate: '12ب345-ایران11',
    total_amount: '1000',
    discount_amount: '0',
    discount_percent: 0,
    net_amount: '1000',
    paid_amount: '0',
    remaining_amount: '1000',
    status: 'DRAFT',
    payment_status: 'UNPAID',
    created_at: '2026-01-01T10:00:00Z',
    tire_items: [],
    service_items: [],
  };

  for (const [role, expected] of [['MANAGER', true], ['TECHNICIAN', true], ['WAREHOUSE', false]] as const) {
    const h = mountComponent('../src/components/invoices/InvoiceDetailModal.tsx', 'InvoiceDetailModal', {
      '../plates/IranianPlateBadge': { IranianPlateBadge: 'plate-badge' },
      '../../utils/formatters': formatters,
      '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { id: 1, role } }) },
      '../../api/invoices': { invoicesApi: { confirmSalesInvoice: async () => {}, cancelSalesInvoice: async () => {} } },
      '../../utils/errorParser': { parseApiError },
    }, { invoice: draftInvoice, onClose() {}, onUpdated() {} });
    t.after(() => h.unmount());

    const canConfirm = nodes(h.tree, (node) => node.type === 'button' && text(node).includes('تایید نهایی و کسر از انبار')).length > 0;
    assert.equal(canConfirm, expected, `Unexpected DRAFT confirm visibility for ${role}`);
  }
});

test('Treasury debounces page reset when searching from page 2 without firing an extra stale request', async (t: TestContext) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const calls: Array<{ page?: number; search?: string }> = [];
  const h = mountComponent('../src/pages/Treasury.tsx', 'Treasury', {
    '../api/finance': {
      financeApi: {
        getReceipts: async (params: { page?: number; search?: string }) => {
          calls.push(params);
          return page([{ receipt_id: 1, customer_name: 'Ali', amount: '1000', payment_method: 'POS', receipt_date: '2026-01-01T10:00:00Z', is_cancelled: false }], params.page ?? 1, 2);
        },
        getPayments: async () => page([]),
        getCustomerRefunds: async () => page([]),
      },
    },
    '../utils/formatters': formatters,
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { id: 1, role: 'MANAGER' } }) },
    '../components/finance/CancelVoucherModal': { CancelVoucherModal: 'cancel-voucher-modal' },
    '../components/finance/PaymentModal': { PaymentModal: 'payment-modal' },
    '../components/finance/CustomerRefundModal': { CustomerRefundModal: 'customer-refund-modal' },
    '../utils/invoiceRequests': invoiceRequests,
    '../utils/errorParser': { parseApiError },
    '../utils/i18n': { translatePaymentMethod },
  });
  t.after(() => h.unmount());
  await h.flush();

  find(h.tree, (node) => node.type === 'button' && text(node) === 'بعدی').props.onClick();
  h.render();
  await h.flush();
  assert.deepEqual(calls, [
    { page: 1, search: undefined },
    { page: 2, search: undefined },
  ]);

  find(h.tree, (node) => node.type === 'input' && node.props['aria-label'] === 'جستجو در اسناد مالی...').props.onChange({
    target: { value: 'ali' },
  });
  h.render();
  await h.flush();
  assert.equal(calls.length, 2, 'Typing search must not immediately fetch page 1 before debounce expires');

  t.mock.timers.tick(350);
  await h.flush();
  assert.deepEqual(calls, [
    { page: 1, search: undefined },
    { page: 2, search: undefined },
    { page: 1, search: 'ali' },
  ]);
});

test('SalesReturnModal preserves unsaved return quantities and reason when language toggles', async (t) => {
  let langState = {
    language: 'fa' as 'fa' | 'en',
    direction: 'rtl' as 'rtl' | 'ltr',
    isRTL: true,
    t: (key: string) => translateMessage(key, 'fa'),
  };
  let returnFetches = 0;
  const invoice = {
    sales_invoice_id: 42,
    invoice_number: 'S-42',
    customer: 1,
    customer_name: 'مشتری',
    customer_phone: '09120000001',
    vehicle: 1,
    license_plate: '12ب345-ایران11',
    total_amount: '2000',
    discount_amount: '0',
    discount_percent: 0,
    net_amount: '2000',
    paid_amount: '2000',
    remaining_amount: '0',
    status: 'CONFIRMED',
    payment_status: 'PAID',
    created_at: '2026-01-01T10:00:00Z',
    tire_items: [{ id: 10, tire: 1, tire_name: 'Tire A', quantity: 4, unit_price: '500' }],
    service_items: [],
  };

  const h = mountComponent('../src/components/invoices/SalesReturnModal.tsx', 'SalesReturnModal', {
    '../../api/invoices': {
      invoicesApi: {
        getSalesReturns: async () => {
          returnFetches++;
          return page([{ return_id: 1, sales_invoice: 42, items: [{ sales_invoice_tire_item: 10, quantity: 1 }] }]);
        },
        createSalesReturn: async () => ({}),
      },
    },
    '../../utils/formatters': formatters,
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial' }) },
    '../../utils/errorParser': { parseApiError },
    '../../context/LanguageContext': { useLanguage: () => langState },
  }, { invoice, onClose() {}, onSuccess() {} });
  t.after(() => h.unmount());
  await h.flush();
  assert.equal(returnFetches, 1);

  find(h.tree, (node) => node.type === 'input' && node.props.type === 'number').props.onChange({
    target: { value: '2' },
  });
  find(h.tree, (node) => node.type === 'textarea' && node.props.id === 'sales-return-reason').props.onChange({
    target: { value: 'Wrong size' },
  });
  h.render();

  langState = {
    language: 'en',
    direction: 'ltr',
    isRTL: false,
    t: (key: string) => translateMessage(key, 'en'),
  };
  h.render();
  await h.flush();

  assert.equal(returnFetches, 1, 'Language toggle must not re-fetch prior sales returns');
  assert.equal(find(h.tree, (node) => node.type === 'input' && node.props.type === 'number').props.value, 2);
  assert.equal(find(h.tree, (node) => node.type === 'textarea' && node.props.id === 'sales-return-reason').props.value, 'Wrong size');
});

test('InvoiceDetailModal A4 and 80mm views compute gross subtotal, effective percentage discount, and zero net_amount', async (t) => {
  const invoice = {
    sales_invoice_id: 77,
    invoice_number: 'S-1405-00077',
    invoice_date: '2026-11-02T12:00:00Z',
    customer: 1,
    customer_name: 'مشتری تخفیف',
    customer_phone: '09120000001',
    vehicle: 1,
    vehicle_plate: '12ب345-ایران11',
    status: 'CONFIRMED',
    payment_status: 'PAID',
    discount_amount: '0.00',
    discount_percent: '10',
    total_amount: '180000',
    returned_amount: '180000',
    net_amount: '0.00',
    tire_items: [
      { id: 1, tire: 1, tire_name: 'Tire 1', brand_name: 'Brand', size_name: '205/55R16', quantity: 2, unit_price: '100000', total_price: '200000' },
    ],
    service_items: [],
  };

  const h = mountComponent('../src/components/invoices/InvoiceDetailModal.tsx', 'InvoiceDetailModal', {
    '../plates/IranianPlateBadge': { IranianPlateBadge: 'plate-badge' },
    '../../utils/formatters': formatters,
    '../../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { id: 1, role: 'MANAGER' } }) },
    '../../api/invoices': { invoicesApi: {} },
    '../../utils/errorParser': { parseApiError },
  }, { invoice, onClose() {}, onUpdated() {} });
  t.after(() => h.unmount());

  const a4Text = text(h.tree);
  assert.match(a4Text, /۲۰۰,۰۰۰ ریال/);
  assert.match(a4Text, /تخفیف:\s*\(10%\)/);
  assert.match(a4Text, /- ۲۰,۰۰۰ ریال/);
  assert.match(a4Text, /مبلغ قابل پرداخت خالص:۰ ریال/);

  const thermalBtn = find(h.tree, (node) => node.type === 'button' && text(node).includes('فیش ۸۰mm'));
  thermalBtn.props.onClick();
  await h.flush();

  const thermalText = text(h.tree);
  assert.match(thermalText, /جمع کل:۲۰۰,۰۰۰ ریال/);
  assert.match(thermalText, /تخفیف:\s*\(10%\)/);
  assert.match(thermalText, /- ۲۰,۰۰۰ ریال/);
  assert.match(thermalText, /مبلغ قابل پرداخت:۰ ریال/);
});
