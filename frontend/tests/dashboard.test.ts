import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseApiError } from '../src/utils/errorParser.ts';
import * as formatters from '../src/utils/formatters.ts';
import { mountComponent, nodes, text } from './componentHarness.ts';

for (const currencyUnit of ['rial', 'toman'] as const) {
  for (const revenues of [[20000000, 10000000, 0], [0, 0], []]) {
    test(`brand chart displays exact ${currencyUnit} amounts and proportional bars: ${revenues}`, async (t) => {
      const h = mountComponent('../src/pages/Dashboard.tsx', 'Dashboard', {
        'react-router-dom': { Link: 'a' },
        '../api/reports': { reportsApi: {
          getDashboardStats: async () => null,
          getSalesByBrand: async () => revenues.map((total_revenue, i) => ({ brand_name: `برند ${i}`, total_revenue })),
          getProfitability: async () => [],
        } },
        '../api/catalog': { catalogApi: { getLowStockTires: async () => [] } },
        '../utils/formatters': formatters,
        '../utils/errorParser': { parseApiError },
        '../context/AuthContext': { useAuth: () => ({ currencyUnit, user: { role: 'MANAGER' } }) },
        '../components/catalog/StockAdjustmentModal': { StockAdjustmentModal: 'stock-adjustment-modal' },
      });
      t.after(() => h.unmount());
      await h.flush();
      const items = nodes(h.tree, (node) => node.props?.className === 'brand-sales-item');
      assert.equal(items.length, revenues.length);
      items.forEach((item, i) => assert.ok(text(item).includes(formatters.formatCurrency(revenues[i], true, currencyUnit))));
      const bars = nodes(h.tree, (node) => node.props?.className === 'brand-sales-bar');
      assert.deepEqual(bars.map((bar) => bar.props.style.width), revenues.map((value) => `${value / Math.max(1, ...revenues) * 100}%`));
      if (!revenues.length) assert.match(text(h.tree), /اطلاعات آماری فروشی جهت نمایش موجود نیست/);
    });
  }
}
