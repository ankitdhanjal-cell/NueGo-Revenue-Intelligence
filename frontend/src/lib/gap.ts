import type { Range } from '../api/types';

/** Seats sold minus the checkpoint range, as a range (negative = behind). */
export function gapRange(sold: number, checkpoint: Range | null): Range | null {
  if (!checkpoint) return null;
  return { low: sold - checkpoint.high, mid: sold - checkpoint.mid, high: sold - checkpoint.low };
}
