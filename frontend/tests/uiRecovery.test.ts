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
