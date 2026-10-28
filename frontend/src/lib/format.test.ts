import { describe, expect, it } from 'vitest';
import { formatINR, formatRange, formatTimeToGo } from './format';

describe('formatINR', () => {
  it('uses Indian grouping', () => {
    expect(formatINR(123456.5)).toBe('₹1,23,456.50');
    expect(formatINR(1234567)).toBe('₹12,34,567');
    expect(formatINR(0)).toBe('₹0');
  });
  it('handles negatives', () => expect(formatINR(-12882)).toBe('-₹12,882'));
  it('never turns a missing value into ₹0', () => {
    expect(formatINR(null)).toBe('—');
    expect(formatINR(undefined)).toBe('—');
    expect(formatINR(Number.NaN)).toBe('—');
  });
});

describe('formatRange', () => {
  it('is mid (low–high)', () =>
    expect(formatRange({ low: 8, mid: 12, high: 16 }, 'seats')).toBe('12 (8–16)'));
  it('keeps negative ranges readable', () =>
    expect(formatRange({ low: -500, mid: -300, high: -100 }, 'inr')).toBe('-₹300 (-₹500 – -₹100)'));
});

describe('formatTimeToGo', () => {
  it('shows days and hours from one day out', () => expect(formatTimeToGo(52.5)).toBe('2 d 4 h'));
  it('shows hours and minutes in the last day', () => expect(formatTimeToGo(3 + 1 / 3)).toBe('3 h 20 m'));
  it('says Departed once it has left', () => expect(formatTimeToGo(-1)).toBe('Departed'));
});
