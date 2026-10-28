import assert from 'node:assert/strict';
import { test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import * as formatters from '../src/utils/formatters.ts';
import { loadComponent } from './componentHarness.ts';

const { IranianPlateBadge } = loadComponent('../src/components/plates/IranianPlateBadge.tsx', {
  '../../utils/formatters': formatters,
});

for (const input of ['12ب345-ایران11', '12 ب 345 ایران 11', '۱۲ب۳۴۵-ایران۱۱', '١٢ب٣٤٥-ایران١١', '12ب345-11', '12ب34511', '12الف345-ایران11']) {
  test(`parses documented and legacy plate format: ${input}`, () => {
    const parsed = formatters.parseIranianPlate(input);
    assert.equal(parsed.isValid, true);
    assert.equal(parsed.part1, '۱۲');
    assert.equal(parsed.part2, '۳۴۵');
    assert.equal(parsed.iranCode, '۱۱');
  });
}

for (const input of [undefined, '', '  ', 'broken', '12،34511', '12134511', '12ب345-ایران', '12345', '<script>']) {
  test(`invalid plate never invents parts: ${String(input)}`, () => {
    assert.deepEqual(formatters.parseIranianPlate(input), { part1: '', letter: '', part2: '', iranCode: '', isValid: false });
    const html = renderToStaticMarkup(React.createElement(IranianPlateBadge, { plateString: input }));
    assert.ok(!html.includes('IRAN'));
    if (input?.trim()) {
      assert.ok(html.includes(input.replaceAll('<', '&lt;').replaceAll('>', '&gt;')));
    } else {
      assert.ok(html.includes('پلاک ثبت نشده است'));
    }
  });
}
