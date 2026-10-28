import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import * as formatters from '../src/utils/formatters.ts';
import { mountComponent, nodes, page, text } from './componentHarness.ts';

type Harness = ReturnType<typeof mountComponent>;

function find(tree: any, predicate: (node: any) => boolean) {
  const node = nodes(tree, predicate)[0];
  assert.ok(node, 'Expected catalog control was not found');
  return node;
}

function labeledField(h: Harness, label: string) {
  const wrapper = find(h.tree, (node) => node.type === 'div' &&
    [node.props.children].flat().some((child) => child?.type === 'label' && text(child).trim() === label));
  return find(wrapper, (node) => node.type === 'input');
}

function change(h: Harness, control: any, value: string) {
  control.props.onChange({ target: { value } });
  h.render();
}

async function setup(t: TestContext, purchasePrice: number | undefined = 70000) {
  const tire = {
    tire_id: 1, tire_name: 'Original tire', brand: 2, brand_name: 'Brand',
    size: 3, size_name: 'Size', stock_quantity: 5, sale_price: 100000,
    purchase_price: purchasePrice, min_stock_alert: 4,
  };
  const updates: Array<{ id: number; data: any }> = [];
  const creations: any[] = [];
  const h = mountComponent('../src/pages/TiresCatalog.tsx', 'TiresCatalog', {
    '../api/catalog': { catalogApi: {
      getTires: async () => page([tire]),
      getBrands: async () => [{ brand_id: 2, brand_name: 'Brand' }],
      getSizes: async () => [{ size_id: 3, size_name: 'Size' }],
      updateTire: async (id: number, data: any) => { updates.push({ id, data }); return tire; },
      createTire: async (data: any) => { creations.push(data); return tire; },
    } },
    '../utils/formatters': formatters,
    '../context/AuthContext': { useAuth: () => ({ currencyUnit: 'rial', user: { role: 'MANAGER' } }) },
    '../components/catalog/StockAdjustmentModal': { StockAdjustmentModal: 'stock-adjustment-modal' },
  });
  t.after(() => h.unmount());
  await h.flush();
  return { h, updates, creations };
}

test('existing tire purchase cost is read-only, explained, and absent from update payload', async (t) => {
  const { h, updates } = await setup(t);
  find(h.tree, (node) => node.props?.title === 'ویرایش نرخ و مشخصات تایر').props.onClick();
  h.render();
  const cost = find(h.tree, (node) => node.props?.id === 'edit-tire-purchase-price');
  assert.equal(cost.props.readOnly, true);
  assert.equal(cost.props.value, 70000);
  assert.equal(cost.props.onChange, undefined);
  const help = find(h.tree, (node) => node.props?.id === cost.props['aria-describedby']);
  assert.match(text(help), /فاکتورهای خرید/);
  assert.match(text(help), /قابل ویرایش نیست/);
  assert.ok(nodes(h.tree, (node) => node.type === 'label' && node.props.htmlFor === cost.props.id).length);

  change(h, labeledField(h, 'نام کامل تایر (گل / مدل):'), 'Updated tire');
  change(h, labeledField(h, 'نرخ فروش پایه کاتالوگ (ریال):'), '120000');
  change(h, labeledField(h, 'حداقل آستانه هشدار کسری انبار (حلقه):'), '6');
  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.deepEqual(updates, [{ id: 1, data: { tire_name: 'Updated tire', sale_price: 120000, min_stock_alert: 6 } }]);
  assert.equal(Object.hasOwn(updates[0].data, 'purchase_price'), false);
});

test('read-only existing tire purchase cost preserves zero', async (t) => {
  const { h } = await setup(t, 0);
  find(h.tree, (node) => node.props?.title === 'ویرایش نرخ و مشخصات تایر').props.onClick();
  h.render();
  const cost = find(h.tree, (node) => node.props?.id === 'edit-tire-purchase-price');
  assert.equal(cost.props.readOnly, true);
  assert.equal(cost.props.value, 0);
});

test('new tire creation retains an editable initial purchase cost and sends its baseline', async (t) => {
  const { h, creations } = await setup(t);
  find(h.tree, (node) => node.type === 'button' && text(node) === 'تعریف تایر جدید').props.onClick();
  h.render();
  const baseline = labeledField(h, 'قیمت خرید اولیه (ریال):');
  assert.ok(!baseline.props.readOnly);
  assert.equal(typeof baseline.props.onChange, 'function');
  change(h, baseline, '80000');
  change(h, labeledField(h, 'نام کامل تایر (گل / مدل):'), 'New tire');
  change(h, labeledField(h, 'قیمت فروش پایه (ریال):'), '150000');
  const selectWithOption = (label: string) => find(h.tree, (node) => node.type === 'select' &&
    nodes(node, (child) => child.type === 'option' && text(child) === label).length > 0);
  change(h, selectWithOption('انتخاب برند...'), '2');
  change(h, selectWithOption('انتخاب سایز...'), '3');
  await find(h.tree, (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  await h.flush();
  assert.deepEqual(creations, [{
    tire_name: 'New tire', brand: 2, size: 3, sale_price: 150000,
    purchase_price: 80000, min_stock_alert: 4,
  }]);
});
