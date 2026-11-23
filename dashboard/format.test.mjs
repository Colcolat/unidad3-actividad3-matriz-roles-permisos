import { test } from 'node:test';
import assert from 'node:assert/strict';
import { money, validPeriod } from './format.mjs';
test('preserva centavos y cantidades mayores que la precisión de Number', () => {
  assert.equal(money('9007199254740993.01'), '$9,007,199,254,740,993.01');
  assert.equal(money('-200.00'), '-$200.00');
  assert.equal(money('0001.2'), '$1.20');
  assert.equal(money('-0.00'), '$0.00');
});
test('no presenta datos inválidos como importes en cero', () => {
  for (const value of [null, '', 'NaN', '1e3', 100, '1.001']) assert.throws(() => money(value));
});
test('valida fechas reales, año bisiesto y orden del período', () => {
  assert.equal(validPeriod('2026-10-26','2026-10-30'), true);
  assert.equal(validPeriod('2026-10-30','2026-10-26'), false);
  assert.equal(validPeriod('2026-02-29','2026-03-01'), false);
  assert.equal(validPeriod('2028-02-29','2028-02-29'), true);
  assert.equal(validPeriod('','2026-03-01'), false);
});
