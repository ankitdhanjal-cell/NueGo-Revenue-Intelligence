import type { Range } from '../api/types';
import { formatRange, type RangeFormat } from '../lib/format';

interface Props {
  range: Range | null | undefined;
  format: RangeFormat;
  missing?: string;
}

/** The only way a predicted number is shown: mid (low–high). No range, no number. */
export default function RangeValue({ range, format, missing = '—' }: Props) {
  if (!range) return <span className="text-slate-400">{missing}</span>;
  return <span className="whitespace-nowrap tabular-nums">{formatRange(range, format)}</span>;
}
