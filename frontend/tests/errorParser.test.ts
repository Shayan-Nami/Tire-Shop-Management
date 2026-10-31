import assert from 'node:assert/strict';
import { test } from 'node:test';
import { AxiosError } from 'axios';
import { parseApiError } from '../src/utils/errorParser.ts';

function failure(data: unknown, status = 400) {
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, {
    data, status, statusText: String(status), headers: {}, config: {} as any,
  });
}

for (const [label, data, expected] of [
  ['wrapped field errors', { success: false, status_code: 400, errors: { phone_number: ['Already registered'] } }, 'شماره تماس: Already registered'],
  ['wrapped detail', { success: false, status_code: 403, errors: { detail: 'Permission denied' } }, 'Permission denied'],
  ['wrapped non-field errors', { errors: { non_field_errors: ['Invalid document'] } }, 'Invalid document'],
  ['nested item errors', { errors: { tire_items: [{ quantity: ['Insufficient stock'] }] } }, 'اقلام تایر: تعداد: Insufficient stock'],
  ['legacy field errors', { amount: ['Above remaining balance'] }, 'مبلغ: Above remaining balance'],
  ['legacy detail', { detail: 'Document cancelled' }, 'Document cancelled'],
  ['message payload', { message: 'Try again' }, 'Try again'],
  ['string payload', 'Invalid request', 'Invalid request'],
  ['array payload', ['First problem', 'Second problem'], 'First problem | Second problem'],
] as const) {
  test(`API error parser handles ${label}`, () => {
    assert.equal(parseApiError(failure(data)), expected);
  });
}

test('API error parser preserves network and timeout messages', () => {
  assert.match(parseApiError(new AxiosError('Network Error', 'ERR_NETWORK')), /برقراری ارتباط/);
  assert.match(parseApiError(new AxiosError('timeout exceeded', 'ECONNABORTED')), /مهلت زمانی/);
});

test('API error parser does not expose server exceptions or HTML responses', () => {
  for (const error of [failure({ detail: 'private database failure' }, 500), failure('<!doctype html><html>private trace</html>')]) {
    const message = parseApiError(error);
    assert.match(message, /خطای داخلی سرور/);
    assert.ok(!message.includes('private'));
  }
});

test('API error parser uses the provided fallback for empty or unrecognized errors', () => {
  for (const error of [undefined, {}, failure({ errors: null }), failure({ errors: {} })]) {
    assert.equal(parseApiError(error, 'Fallback message'), 'Fallback message');
  }
  assert.equal(parseApiError(new Error('Client validation')), 'Client validation');
});

test('API error parser safely handles cyclic error payloads', () => {
  const errors: Record<string, unknown> = { detail: 'Known problem' };
  errors.cycle = errors;
  assert.equal(parseApiError(failure({ errors })), 'Known problem');
});
