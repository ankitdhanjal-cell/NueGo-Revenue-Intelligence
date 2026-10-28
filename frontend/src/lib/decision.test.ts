import { describe, expect, it } from 'vitest';
import { validateDecision } from './decision';

const form = { fare: null, reason: '', category: '' };

describe('validateDecision', () => {
  it('approve needs nothing', () => expect(validateDecision('approve', form, [])).toEqual({}));
  it('reject needs a reason', () => {
    expect(validateDecision('reject', form, [])).toHaveProperty('reason');
    expect(validateDecision('reject', { ...form, reason: '  ' }, [])).toHaveProperty('reason');
    expect(validateDecision('reject', { ...form, reason: 'Festival' }, [])).toEqual({});
  });
  it('change needs an allowed fare and a reason', () => {
    expect(validateDecision('change', { ...form, reason: 'x' }, [400])).toHaveProperty('fare');
    expect(validateDecision('change', { fare: 410, reason: 'x', category: '' }, [400])).toHaveProperty(
      'fare',
    );
    expect(validateDecision('change', { fare: 400, reason: 'x', category: '' }, [400])).toEqual({});
  });
  it('wrong needs a category and a reason', () => {
    expect(Object.keys(validateDecision('wrong', form, []))).toEqual(['category', 'reason']);
  });
});
