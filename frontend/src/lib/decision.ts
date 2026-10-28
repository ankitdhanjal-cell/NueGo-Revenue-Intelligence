import type { DecisionAction } from '../api/types';

interface DecisionForm {
  fare: number | null;
  reason: string;
  category: string;
}

/** Field errors for a decision. An empty object means it can be submitted. */
export function validateDecision(
  action: DecisionAction,
  form: DecisionForm,
  allowedFares: number[],
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (action === 'change' && (form.fare == null || !allowedFares.includes(form.fare))) {
    errors.fare = 'Choose an allowed fare step that passes the rules.';
  }
  if (action === 'wrong' && !form.category) errors.category = 'Choose a category.';
  if (action !== 'approve' && !form.reason.trim()) errors.reason = 'A reason is required.';
  return errors;
}
