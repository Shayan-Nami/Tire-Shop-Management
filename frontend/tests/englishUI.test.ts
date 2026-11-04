import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import ts from 'typescript';
import { translations } from '../src/utils/i18n.ts';
import * as formatters from '../src/utils/formatters.ts';
import { parseApiError } from '../src/utils/errorParser.ts';
import { mountComponent, nodes, text } from './componentHarness.ts';

test('every static translation key in UI source has an English translation', () => {
  const missing: string[] = [];
  function walk(dir: URL) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const url = new URL(entry.name + (entry.isDirectory() ? '/' : ''), dir);
      if (entry.isDirectory()) walk(url);
      else if (entry.name.endsWith('.tsx')) {
        const source = ts.createSourceFile(fileURLToPath(url), readFileSync(url, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
        function visit(node: ts.Node) {
          if (ts.isCallExpression(node) && node.expression.getText(source) === 't' && ts.isStringLiteral(node.arguments[0])) {
            const key = node.arguments[0].text;
            if (!translations[key]?.en?.trim()) missing.push(`${entry.name}: ${key}`);
          }
          ts.forEachChild(node, visit);
        }
        visit(source);
      }
    }
  }
  walk(new URL('../src/', import.meta.url));
  assert.deepEqual(missing, []);
});

test('English currency labels and digits preserve the existing rial/toman conversion', () => {
  assert.equal(formatters.formatCurrency(1234560, true, 'rial', 'en'), '1,234,560 IRR');
  assert.equal(formatters.formatCurrency('1234560.00', true, 'toman', 'en'), '123,456 Toman');
  assert.equal(formatters.formatCurrency(0, true, 'rial', 'en'), '0 IRR');
  assert.equal(formatters.formatCurrency(null, true, 'rial', 'en'), '0');
  assert.equal(formatters.formatCurrency(1234560, true, 'rial', 'fa'), '۱,۲۳۴,۵۶۰ ریال');
  assert.equal(formatters.formatCurrency(1000, false, 'rial', 'en'), '1,000');
});

test('English dates use the Gregorian calendar while Persian dates stay Jalali', () => {
  const date = '2026-11-02T12:00:00Z';
  assert.match(formatters.formatIsoToJalali(date, 'en'), /2026/);
  assert.match(formatters.formatIsoToJalali(date, 'fa'), /۱۴۰۵/);
  assert.equal(formatters.formatIsoToJalali(null, 'en'), '-');
  assert.equal(formatters.formatIsoToJalali('invalid', 'en'), 'invalid');
});

test('English network errors and field labels are readable without losing server validation details', () => {
  const network = { isAxiosError: true, code: 'ERR_NETWORK', message: 'Network Error' };
  assert.match(parseApiError(network, undefined, 'en'), /Cannot connect/);
  const validation = { isAxiosError: true, message: 'Bad request', response: {
    status: 400, data: { errors: { phone_number: ['Enter a valid phone number.'] } },
  } };
  assert.equal(parseApiError(validation, undefined, 'en'), 'phone number: Enter a valid phone number.');
});

test('English dashboard translates controls and currency but preserves shop data', async (t) => {
  const language = {
    language: 'en', direction: 'ltr', isRTL: false,
    t: (key: string, fallback?: string) => translations[key]?.en || fallback || key,
  };
  const h = mountComponent('../src/pages/Dashboard.tsx', 'Dashboard', {
    'react-router-dom': { Link: 'a' },
    '../context/LanguageContext': { useLanguage: () => language },
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { role: 'MANAGER' } }) },
    '../api/reports': { reportsApi: {
      getDashboardStats: async () => null,
      getSalesByBrand: async () => [{ brand_name: 'برند مشتری', total_revenue: 1234560 }],
      getProfitability: async () => [],
    } },
    '../api/catalog': { catalogApi: { getLowStockTires: async () => [] } },
    '../utils/formatters': formatters,
    '../utils/errorParser': { parseApiError },
    '../components/catalog/StockAdjustmentModal': { StockAdjustmentModal: 'stock-adjustment-modal' },
  });
  t.after(() => h.unmount());
  await h.flush();
  assert.match(text(h.tree), /Shop dashboard/);
  assert.match(text(h.tree), /Net sales by tire brand/);
  assert.match(text(h.tree), /1,234,560 IRR/);
  assert.match(text(h.tree), /برند مشتری/);
  assert.ok(!text(h.tree).includes('نیازمند رسیدگی'));
});

test('switching an open profile form to English keeps unsaved input', async (t) => {
  let locale: 'fa' | 'en' = 'fa';
  const user = { id: 1, username: 'manager', full_name: 'Original name', role: 'MANAGER' };
  const h = mountComponent('../src/components/auth/ProfileModal.tsx', 'ProfileModal', {
    '../../context/LanguageContext': { useLanguage: () => ({
      language: locale, t: (key: string) => translations[key]?.[locale] || key,
    }) },
    '../../context/AuthContext': { useAuth: () => ({ user, updateUser() {} }) },
    '../../api/auth': { authApi: {} }, '../../utils/errorParser': { parseApiError },
  }, { isOpen: true, onClose() {} });
  t.after(() => h.unmount());
  await h.flush();
  const nameInput = nodes(h.tree, (node) => node.type === 'input' && node.props.value === 'Original name')[0];
  nameInput.props.onChange({ target: { value: 'Unsaved edit' } });
  await h.flush();
  locale = 'en';
  h.render();
  assert.match(text(h.tree), /Edit profile/);
  assert.equal(nodes(h.tree, (node) => node.type === 'input' && node.props.value === 'Unsaved edit').length, 1);
});

test('A4 and thermal invoice views use English labels, amounts and statuses', async (t) => {
  const language = { language: 'en', t: (key: string) => translations[key]?.en || key };
  const h = mountComponent('../src/components/invoices/InvoiceDetailModal.tsx', 'InvoiceDetailModal', {
    '../../context/LanguageContext': { useLanguage: () => language },
    '../../context/AuthContext': { useAuth: () => ({ user: { role: 'MANAGER' }, currencyUnit: 'rial' }) },
    '../../api/invoices': { invoicesApi: {} },
    '../../utils/formatters': formatters, '../../utils/errorParser': { parseApiError },
    '../plates/IranianPlateBadge': { IranianPlateBadge: 'plate-badge' },
  }, { invoice: {
    sales_invoice_id: 1, invoice_number: 'S-1405-00001', invoice_date: '2026-11-02T12:00:00Z',
    status: 'CONFIRMED', status_display: 'تایید شده', payment_status: 'UNPAID', payment_status_display: 'تسویه نشده',
    customer_name: 'Customer', tire_items: [], service_items: [], total_amount: '1000', net_amount: '1000',
  }, onClose() {}, onUpdated() {} });
  t.after(() => h.unmount());
  await h.flush();
  assert.match(text(h.tree), /Confirmed/);
  assert.match(text(h.tree), /Unpaid/);
  assert.match(text(h.tree), /Customer details/);
  assert.match(text(h.tree), /1,000 IRR/);
  const thermal = nodes(h.tree, (node) => node.type === 'button' && node.props.title === 'View and print an 80 mm thermal receipt')[0];
  assert.ok(thermal);
  thermal.props.onClick();
  await h.flush();
  assert.match(text(h.tree), /Customer receipt \(80 mm\)/);
  assert.match(text(h.tree), /Thank you for choosing us/);
});
