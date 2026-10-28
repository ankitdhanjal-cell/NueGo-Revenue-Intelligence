import { formatINR } from '../lib/format';

interface Props {
  value: number | null | undefined;
  missing?: string;
  colorNegative?: boolean;
}

export default function Money({ value, missing = '—', colorNegative = false }: Props) {
  if (value == null) return <span className="text-slate-400">{missing}</span>;
  const tone = colorNegative && value < 0 ? 'text-bad' : '';
  return <span className={`whitespace-nowrap tabular-nums ${tone}`}>{formatINR(value)}</span>;
}
