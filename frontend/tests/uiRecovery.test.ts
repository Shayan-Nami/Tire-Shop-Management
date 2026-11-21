import assert from 'node:assert/strict';
import { test } from 'node:test';
import * as formatters from '../src/utils/formatters.ts';
import { parseApiError } from '../src/utils/errorParser.ts';
import { mountComponent, nodes, text } from './componentHarness.ts';

for (const component of ['Dashboard', 'ReportsPage']) {
  test(`${component} shows a failed request and supports retry instead of empty financial data`, async (t) => {
    let failing = true;
    const request = async () => {
      if (failing) throw new Error('offline');
      return [];
    };
    const h = mountComponent(`../src/pages/${component}.tsx`, component, {
      'react-router-dom': { Link: 'a' },
      '../api/reports': { reportsApi: {
        getDashboardStats: request, getSalesByBrand: request, getProfitability: request,
      } },
      '../api/catalog': { catalogApi: { getLowStockTires: request } },
      '../utils/formatters': formatters,
      '../utils/errorParser': { parseApiError },
      '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { role: 'MANAGER' } }) },
      '../components/catalog/StockAdjustmentModal': { StockAdjustmentModal: 'stock-adjustment-modal' },
    });
    t.after(() => h.unmount());
    await h.flush();
    const alerts = nodes(h.tree, (node) => node.props?.role === 'alert');
    assert.equal(alerts.length, 1);
    assert.match(text(alerts[0]), /offline/);
    assert.equal(nodes(h.tree, (node) => node.type === 'table').length, 0);
    failing = false;
    nodes(alerts[0], (node) => node.type === 'button')[0].props.onClick();
    await h.flush();
    assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);
  });
}

test('navigation resets workspace scroll only when the path changes', (t) => {
  let pathname = '/dashboard';
  const scrollCalls: number[][] = [];
  const h = mountComponent('../src/components/layout/MainLayout.tsx', 'MainLayout', {
    'react-router-dom': { Outlet: 'outlet', useLocation: () => ({ pathname }) },
    './Sidebar': { Sidebar: 'sidebar' }, './Navbar': { Navbar: 'navbar' },
  });
  t.after(() => h.unmount());
  nodes(h.tree, (node) => node.type === 'main')[0].props.ref.current = {
    scrollTo: (...args: number[]) => scrollCalls.push(args),
  };
  h.render();
  assert.deepEqual(scrollCalls, []);
  pathname = '/customers';
  h.render();
  assert.deepEqual(scrollCalls, [[0, 0]]);
});

test('ReportsPage keeps by_date filter form editable on 400 error and recovers on corrected submit', async (t) => {
  const calls: Array<{ start?: string; end?: string }> = [];
  let failOnce = true;
  const h = mountComponent('../src/pages/ReportsPage.tsx', 'ReportsPage', {
    '../api/reports': {
      reportsApi: {
        getProfitability: async () => [],
        getInventoryValue: async () => ({ total_inventory_value: 0, items: [] }),
        getSalesByDateRange: async (start?: string, end?: string) => {
          calls.push({ start, end });
          if (failOnce) throw new Error('تاریخ پایان نامعتبر است');
          return { total_invoices: 3, total_sales_amount: 950000 };
        },
      },
    },
    '../utils/formatters': formatters,
    '../utils/errorParser': { parseApiError },
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { role: 'MANAGER' } }) },
  });
  t.after(() => h.unmount());
  await h.flush();

  const dateTab = nodes(h.tree, (node) => node.type === 'button')[2];
  dateTab.props.onClick();
  h.render();
  await h.flush();

  const findById = (id: string) => nodes(h.tree, (node) => node.props?.id === id)[0];
  findById('reports-start-date').props.onChange({ target: { value: '1404/01/01' } });
  findById('reports-end-date').props.onChange({ target: { value: 'invalid-date' } });
  h.render();

  await nodes(h.tree, (node) => node.type === 'form')[0].props.onSubmit({ preventDefault() {} });
  await h.flush();

  const alerts = nodes(h.tree, (node) => node.props?.role === 'alert');
  assert.equal(alerts.length, 1);
  assert.match(text(alerts[0]), /تاریخ پایان نامعتبر است/);
  assert.ok(findById('reports-start-date'), 'Date range form must remain mounted after validation error');
  assert.equal(findById('reports-start-date').props.value, '1404/01/01');
  assert.equal(findById('reports-end-date').props.value, 'invalid-date');

  failOnce = false;
  findById('reports-end-date').props.onChange({ target: { value: '1404/01/31' } });
  h.render();
  await nodes(h.tree, (node) => node.type === 'form')[0].props.onSubmit({ preventDefault() {} });
  await h.flush();

  assert.equal(nodes(h.tree, (node) => node.props?.role === 'alert').length, 0);
  assert.match(text(h.tree), /۹۵۰,۰۰۰/);
  assert.equal(calls[calls.length - 1].end, '1404/01/31');
});
