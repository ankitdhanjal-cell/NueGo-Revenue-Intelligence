/** Fare-steps rules, mirroring the API: positive, unique, ascending. */
export function validateFareSteps(steps: number[]): string[] {
  if (steps.length === 0) return ['Add at least one fare step.'];
  const errors: string[] = [];
  if (steps.some((s) => !Number.isFinite(s) || s <= 0)) errors.push('Fare steps must be positive numbers.');
  else if (steps.some((s, i) => i > 0 && s <= (steps[i - 1] ?? 0)))
    errors.push('Fare steps must be unique and ascending.');
  return errors;
}

export function generateFareSteps(from: number, to: number, every: number): number[] {
  if (!(from > 0) || !(every > 0) || to < from) return [];
  const out: number[] = [];
  for (let f = from; f <= to + 1e-9; f += every) out.push(Math.round(f * 100) / 100);
  return out;
}

export function parseFareSteps(text: string): number[] {
  return text
    .split(/[\s,]+/)
    .filter(Boolean)
    .map(Number);
}
