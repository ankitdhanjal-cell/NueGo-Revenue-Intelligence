import { describe, expect, it } from 'vitest';
import { generateFareSteps, parseFareSteps, validateFareSteps } from './fareSteps';

describe('validateFareSteps', () => {
  it('accepts positive, unique, ascending steps', () =>
    expect(validateFareSteps([200, 210, 250])).toEqual([]));
  it('rejects an empty list', () => expect(validateFareSteps([])).not.toEqual([]));
  it('rejects zero, negative and non-numbers', () => {
    expect(validateFareSteps([0, 10])).not.toEqual([]);
    expect(validateFareSteps([-5, 10])).not.toEqual([]);
    expect(validateFareSteps([Number.NaN])).not.toEqual([]);
  });
  it('rejects duplicates and descending order', () => {
    expect(validateFareSteps([200, 200])).not.toEqual([]);
    expect(validateFareSteps([300, 200])).not.toEqual([]);
  });
});

describe('generateFareSteps and parseFareSteps', () => {
  it('generates from, to, every', () =>
    expect(generateFareSteps(200, 230, 10)).toEqual([200, 210, 220, 230]));
  it('returns nothing for impossible input', () => {
    expect(generateFareSteps(300, 200, 10)).toEqual([]);
    expect(generateFareSteps(200, 300, 0)).toEqual([]);
  });
  it('parses commas, spaces and lines', () =>
    expect(parseFareSteps('200, 210\n220 230')).toEqual([200, 210, 220, 230]));
});
